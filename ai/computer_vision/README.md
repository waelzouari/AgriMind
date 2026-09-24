# Computer vision dataset and training pipeline

AGM-030 implements the reproducible binary `NORMAL` / `ANOMALY` training
boundary. It does not diagnose disease or implement image upload, inference
APIs, cameras, robotics, or irrigation behavior.

## Approved notebook dataset

The supplied Colab notebook clones
[`gabrieldgf4/PlantVillage-Dataset`](https://github.com/gabrieldgf4/PlantVillage-Dataset).
AGM-030 pins commit `825c387b026b01570caa85ab7fdba5cb594adab0`
instead of following its moving default branch. The mirror documents that it
republishes upstream PlantVillage images. The pinned tree actually contains
54,300 accepted images in 38 crop/condition folders: 15,079 map to `NORMAL` and
39,221 map to `ANOMALY`, despite the mirror README claiming 54,304 images.
It also holds five explicitly rejected healthy
images in `x_Removed_from_Healthy_leaves`; these are not training data.

The mirror has no license file. Its upstream Mendeley distribution identifies
the data as CC0 1.0; this provenance gap is retained as a limitation rather
than presenting the mirror itself as independently licensed.

Obtain the pinned source outside Git:

```bash
git clone https://github.com/gabrieldgf4/PlantVillage-Dataset.git \
  ai/computer_vision/data/raw/plantvillage-notebook-mirror
git -C ai/computer_vision/data/raw/plantvillage-notebook-mirror \
  checkout 825c387b026b01570caa85ab7fdba5cb594adab0
```

Audit it without modifying source images:

```bash
python -m agrimind_cv.cli audit \
  --config ai/computer_vision/configs/datasets/plantvillage-notebook-mirror-v1.json \
  --dataset-root ai/computer_vision/data/raw/plantvillage-notebook-mirror \
  --report ai/computer_vision/data/interim/plantvillage-audit.json \
  --manifest ai/computer_vision/data/interim/plantvillage-manifest.csv
```

The mapping is an explicit 38-entry configuration. Unknown folders fail
closed. The canonical full profile has no 300-image cap; generated images are
used only by CI.

## Split and model selection

The split is seeded, deterministic, stratified by binary label, and groups
exact hashes so identical bytes cannot cross partitions. The mirror lacks
trustworthy physical-leaf metadata, so residual related-image leakage remains
possible and is documented. Augmentation occurs only after splitting.

The simple baseline classifies validation images by nearest training-class
mean-RGB centroid. The selected candidate is ImageNet-pretrained MobileNetV2 at
224×224 with RGB input, ImageNet normalization, CHW float32 tensors, and seeded
horizontal flips during training only. Checkpoint selection uses validation
loss. The held-out test partition, formal metrics, threshold trade-offs, and
inference API belong to AGM-031.

Install full training dependencies explicitly:

```bash
python -m pip install -e "./ai/computer_vision[train]"
```

Then run the complete AGM-030 audit, split, baseline, and MobileNetV2
validation-selection workflow (the held-out test partition remains untouched):

```bash
python -m agrimind_cv.cli train \
  --dataset-config ai/computer_vision/configs/datasets/plantvillage-notebook-mirror-v1.json \
  --training-config ai/computer_vision/configs/training/mobilenet-v2-v1.json \
  --dataset-root ai/computer_vision/data/raw/plantvillage-notebook-mirror \
  --model ai/computer_vision/artifacts/agm-030-mobilenet-v2.pt \
  --metadata ai/computer_vision/artifacts/agm-030-mobilenet-v2.metadata.json \
  --artifact-id agm-030-mobilenet-v2 \
  --code-revision "$(git rev-parse HEAD)"
```

Generated manifests, datasets, checkpoints, and metadata remain under ignored
`data/` and `artifacts/` paths. Ordinary CI uses no Internet, GPU, camera,
Raspberry Pi, GPIO, or public dataset.

## Required limitation

PlantVillage contains predominantly clean, controlled single-leaf imagery.
Performance on it does not prove equivalent performance on AgriMind smartphone
images, field backgrounds, different illumination, occluded or multiple leaves,
Morus alba, Tunisian farms, or unseen species. The output is screening status,
not a disease name or agronomic recommendation.
