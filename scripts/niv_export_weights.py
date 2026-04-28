"""
Export NIV training checkpoints into the binary format consumed by Falcor's
NeuralIrradianceVolume render pass.

The `neural-irradiance-volume/` submodule is the upstream training repo. Falcor
reads ONLY the .pt checkpoint and the matching default.yaml from there; it never
imports any of the submodule's runtime code at viewer time.

Layout (little-endian, single .bin file):

    Header (128 bytes, padded for cache-line alignment and future fields):
        magic           u32    'NIVW' = 0x5747494E
        version         u32    1
        numLevels       u32    e.g. 8
        hashTableSize   u32    e.g. 131072
        featureDim      u32    e.g. 4
        mlpLayers       u32    e.g. 4
        mlpHidden       u32    e.g. 64
        inputDim        u32    e.g. 35  (numLevels*featureDim + 3)
        outputDim       u32    e.g. 3
        weightLayout    u32    0 = RowMajor, 1 = InferencingOptimal (this exporter writes 0)
        aabbMin         f32 x 3
        aabbMax         f32 x 3
        weightBytes     u32    size of weight blob (post-alignment)
        biasBytes       u32    size of bias blob (post-alignment)
        _pad            u32 x 14   (reserved; zeroed)

    int32   resolutions[numLevels]
    uint32  hashTables[numLevels * hashTableSize * featureDim/2]   # fp16 pairs packed in u32
    uint32  weightOffsets[mlpLayers]   # byte offsets into weight blob
    uint32  biasOffsets[mlpLayers]     # byte offsets into bias blob
    byte    weightBlob[weightBytes]    # fp16 row-major matrices, per-layer 64-byte aligned
    byte    biasBlob[biasBytes]        # fp16 biases, per-layer 16-byte aligned

The Slang shader in Falcor reads weightBlob via ByteAddressBuffer and runs
coopVecMatMulAdd with CoopVecMatrixLayout.RowMajor. If we later decide to
swap to InferencingOptimal we will add a conversion step at scene-load
time on the C++ side; the offline export remains hardware-independent.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

try:
    import torch
except ImportError:
    sys.stderr.write("ERROR: torch is required. Install via: pip install torch\n")
    sys.exit(2)

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: pyyaml is required. Install via: pip install pyyaml\n")
    sys.exit(2)


MAGIC = 0x5747494E  # 'NIVW' little-endian
VERSION = 1
LAYOUT_ROW_MAJOR = 0
LAYOUT_INFERENCING_OPTIMAL = 1

WEIGHT_ALIGN = 64
BIAS_ALIGN = 16


def _align(off: int, alignment: int) -> int:
    return (off + alignment - 1) & ~(alignment - 1)


def export(checkpoint_path: Path, config_path: Path, out_path: Path) -> None:
    print(f"[niv-export] checkpoint: {checkpoint_path}")
    print(f"[niv-export] config:     {config_path}")

    ckpt = torch.load(str(checkpoint_path), map_location="cpu", weights_only=False)
    sd = ckpt["model_state_dict"]
    cfg_ckpt = ckpt.get("config", {})

    with open(config_path, "r") as f:
        cfg_yaml = yaml.safe_load(f)

    model_cfg = cfg_ckpt.get("model", cfg_yaml.get("model", {}))
    hash_cfg = model_cfg.get("hash_encoding", {})

    num_levels = int(model_cfg.get("hash_num_levels", hash_cfg.get("num_levels", 8)))
    hash_table_size_log2 = int(model_cfg.get("hash_table_size_log2", hash_cfg.get("hash_table_size_log2", 17)))
    hash_table_size = 1 << hash_table_size_log2
    feature_dim = int(model_cfg.get("hash_feature_dim", hash_cfg.get("feature_dim", 4)))
    mlp_hidden = int(model_cfg.get("mlp_width", 64))
    mlp_layers = int(model_cfg.get("mlp_depth", 4))
    output_dim = int(model_cfg.get("output_dim", 3))
    input_dim = num_levels * feature_dim + 3  # hash features + 3D normal

    # AABB: prefer values stored in the checkpoint; fall back to config.
    if "bounds_min" in sd and "bounds_max" in sd:
        aabb_min = sd["bounds_min"].cpu().numpy().astype(np.float32).reshape(3)
        aabb_max = sd["bounds_max"].cpu().numpy().astype(np.float32).reshape(3)
    else:
        scene_cfg = cfg_yaml.get("scene", {})
        aabb_min = np.array(scene_cfg.get("bounds_min", [0, 0, 0]), dtype=np.float32)
        aabb_max = np.array(scene_cfg.get("bounds_max", [1, 1, 1]), dtype=np.float32)

    # Per-level resolutions (precomputed during training).
    if "position_encoding.resolutions" in sd:
        resolutions = sd["position_encoding.resolutions"].cpu().numpy().astype(np.int32).reshape(-1)
    else:
        coarsest = int(hash_cfg.get("coarsest_resolution", 16))
        scale = float(hash_cfg.get("scale_factor", 1.4142))
        resolutions = np.array(
            [int(round(coarsest * (scale ** i))) for i in range(num_levels)],
            dtype=np.int32,
        )

    if resolutions.size != num_levels:
        raise ValueError(f"resolutions length {resolutions.size} != numLevels {num_levels}")

    # Hash tables (fp16 features) → packed as u32 pairs (matches niv_composite.slang).
    hash_data = sd["position_encoding.hash_table.weight"].cpu().numpy().astype(np.float16)
    expected = (num_levels * hash_table_size, feature_dim)
    if hash_data.shape != expected:
        raise ValueError(f"hash table shape {hash_data.shape} != expected {expected}")
    if feature_dim % 2 != 0:
        raise ValueError(f"featureDim must be even (was {feature_dim})")
    hash_packed = hash_data.view(np.uint32).reshape(-1)  # (N*L*F/2,) uint32

    # MLP weights/biases: keys are mlp.network.{0,2,4,6}.* (Linear layers separated by ReLU).
    mlp_indices = list(range(0, 2 * mlp_layers, 2))
    weight_keys = [f"mlp.network.{i}.weight" for i in mlp_indices]
    bias_keys = [f"mlp.network.{i}.bias" for i in mlp_indices]
    for key in weight_keys + bias_keys:
        if key not in sd:
            raise KeyError(f"missing tensor in checkpoint: {key}")

    weight_arrays = [sd[k].cpu().numpy().astype(np.float16) for k in weight_keys]
    bias_arrays = [sd[k].cpu().numpy().astype(np.float16) for k in bias_keys]

    # Sanity checks against declared dims.
    expected_shapes = [
        (mlp_hidden, input_dim),
        *[(mlp_hidden, mlp_hidden) for _ in range(mlp_layers - 2)],
        (output_dim, mlp_hidden),
    ]
    for i, (W, expected_shape) in enumerate(zip(weight_arrays, expected_shapes)):
        if W.shape != expected_shape:
            raise ValueError(f"layer {i}: weight shape {W.shape} != expected {expected_shape}")
    for i, (B, layer_out) in enumerate(zip(bias_arrays, [s[0] for s in expected_shapes])):
        if B.shape != (layer_out,):
            raise ValueError(f"layer {i}: bias shape {B.shape} != expected ({layer_out},)")

    # Pack weights with 64-byte alignment between layers.
    weight_blob = bytearray()
    weight_offsets = []
    for W in weight_arrays:
        off = _align(len(weight_blob), WEIGHT_ALIGN)
        weight_blob.extend(b"\x00" * (off - len(weight_blob)))
        weight_offsets.append(off)
        weight_blob.extend(W.tobytes())
    weight_bytes = len(weight_blob)

    # Pack biases with 16-byte alignment.
    bias_blob = bytearray()
    bias_offsets = []
    for B in bias_arrays:
        off = _align(len(bias_blob), BIAS_ALIGN)
        bias_blob.extend(b"\x00" * (off - len(bias_blob)))
        bias_offsets.append(off)
        bias_blob.extend(B.tobytes())
    bias_bytes = max(len(bias_blob), 16)
    if len(bias_blob) < bias_bytes:
        bias_blob.extend(b"\x00" * (bias_bytes - len(bias_blob)))

    # ----- Header (128 bytes; trailing 48 bytes reserved for future fields) -----
    header = struct.pack(
        "<10I 3f 3f 2I 14I",
        MAGIC, VERSION,
        num_levels, hash_table_size, feature_dim,
        mlp_layers, mlp_hidden, input_dim, output_dim,
        LAYOUT_ROW_MAJOR,
        float(aabb_min[0]), float(aabb_min[1]), float(aabb_min[2]),
        float(aabb_max[0]), float(aabb_max[1]), float(aabb_max[2]),
        weight_bytes, bias_bytes,
        *([0] * 14),  # reserved padding
    )
    assert len(header) == 128, f"header size {len(header)} != 128"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(header)
        f.write(resolutions.tobytes())
        f.write(hash_packed.tobytes())
        f.write(np.array(weight_offsets, dtype=np.uint32).tobytes())
        f.write(np.array(bias_offsets, dtype=np.uint32).tobytes())
        f.write(bytes(weight_blob))
        f.write(bytes(bias_blob))

    total = out_path.stat().st_size
    print(f"[niv-export] wrote {out_path} ({total / 1024 / 1024:.2f} MB)")
    print(f"[niv-export]   numLevels={num_levels} hashTableSize={hash_table_size} "
          f"featureDim={feature_dim}")
    print(f"[niv-export]   mlp {mlp_layers}x{mlp_hidden} (in={input_dim} out={output_dim})")
    print(f"[niv-export]   AABB min={aabb_min.tolist()} max={aabb_max.tolist()}")
    print(f"[niv-export]   weightBytes={weight_bytes} biasBytes={bias_bytes}")
    print(f"[niv-export]   weightOffsets={weight_offsets}")
    print(f"[niv-export]   biasOffsets={bias_offsets}")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    default_ckpt = repo_root / "neural-irradiance-volume" / "checkpoints" / "niv_breakfast_room.pt"
    default_cfg = repo_root / "neural-irradiance-volume" / "configs" / "default.yaml"
    default_out = repo_root / "media" / "niv_weights" / "breakfast_room.bin"

    p = argparse.ArgumentParser(description="Export NIV PyTorch checkpoint to Falcor binary.")
    p.add_argument("--checkpoint", type=Path, default=default_ckpt)
    p.add_argument("--config", type=Path, default=default_cfg)
    p.add_argument("--out", type=Path, default=default_out)
    args = p.parse_args()

    if not args.checkpoint.exists():
        sys.stderr.write(f"checkpoint not found: {args.checkpoint}\n")
        sys.exit(1)
    if not args.config.exists():
        sys.stderr.write(f"config not found: {args.config}\n")
        sys.exit(1)

    export(args.checkpoint, args.config, args.out)


if __name__ == "__main__":
    main()
