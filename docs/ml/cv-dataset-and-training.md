# AGM-030 CV evidence and boundaries

## Implemented

- Exact `NORMAL` (0) / `ANOMALY` (1) target contract.
- Explicit mapping for all 38 intended PlantVillage source folders.
- Pinned notebook-mirror revision and provenance metadata.
- Immutable audit, canonical manifest, duplicate reporting, and fingerprints.
- Seeded, label-stratified, exact-duplicate-group-preserving 70/15/15 split.
- Versioned RGB 224×224/ImageNet preprocessing and training-only augmentation.
- Mean-RGB centroid baseline and MobileNetV2 validation-selection boundary.
- Atomic, non-overwriting artifact metadata.
- Offline, hardware-independent contract tests.

## Notebook adaptation

The approved notebook was inspected rather than copied. It clones the
unversioned `gabrieldgf4/PlantVillage-Dataset` default branch, recursively
discovers image directories, infers healthy labels using substring matching,
caps every source class at 300, performs image-level 70/15/15 splits, and trains
a frozen ImageNet MobileNetV2 head. It selects a checkpoint and threshold on
validation, evaluates test, and exports Keras/TFLite artifacts.

AGM-030 pins commit `825c387b026b01570caa85ab7fdba5cb594adab0`, removes
the cap, replaces substring inference with a versioned mapping, groups exact
duplicates before splitting, and excludes the mirror's five explicitly rejected
healthy images. Formal test evaluation, threshold evidence, and inference/TFLite
integration remain AGM-031 work.

## Verified source census

The pinned Git tree contains the 38 configured folders with 54,300 accepted
images: 12 healthy and 26 affected source classes across 14 crop species. It
also contains the separate five-image rejection folder described by the mirror
README. The measured tree total is 54,305, despite the README claiming 54,304. Tree
counts are provenance evidence, not a substitute for decoding and hashing a
local checkout.

| Source folder | Binary label | Git-tree count |
|---|---:|---:|
| Apple___Apple_scab | ANOMALY | 630 |
| Apple___Black_rot | ANOMALY | 621 |
| Apple___Cedar_apple_rust | ANOMALY | 275 |
| Apple___healthy | NORMAL | 1,645 |
| Blueberry___healthy | NORMAL | 1,502 |
| Cherry_(including_sour)___healthy | NORMAL | 853 |
| Cherry_(including_sour)___Powdery_mildew | ANOMALY | 1,052 |
| Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot | ANOMALY | 513 |
| Corn_(maize)___Common_rust_ | ANOMALY | 1,192 |
| Corn_(maize)___healthy | NORMAL | 1,162 |
| Corn_(maize)___Northern_Leaf_Blight | ANOMALY | 985 |
| Grape___Black_rot | ANOMALY | 1,180 |
| Grape___Esca_(Black_Measles) | ANOMALY | 1,383 |
| Grape___healthy | NORMAL | 423 |
| Grape___Leaf_blight_(Isariopsis_Leaf_Spot) | ANOMALY | 1,076 |
| Orange___Haunglongbing_(Citrus_greening) | ANOMALY | 5,507 |
| Peach___Bacterial_spot | ANOMALY | 2,297 |
| Peach___healthy | NORMAL | 360 |
| Pepper,_bell___Bacterial_spot | ANOMALY | 997 |
| Pepper,_bell___healthy | NORMAL | 1,476 |
| Potato___Early_blight | ANOMALY | 1,000 |
| Potato___healthy | NORMAL | 152 |
| Potato___Late_blight | ANOMALY | 1,000 |
| Raspberry___healthy | NORMAL | 371 |
| Soybean___healthy | NORMAL | 5,089 |
| Squash___Powdery_mildew | ANOMALY | 1,835 |
| Strawberry___healthy | NORMAL | 456 |
| Strawberry___Leaf_scorch | ANOMALY | 1,109 |
| Tomato___Bacterial_spot | ANOMALY | 2,127 |
| Tomato___Early_blight | ANOMALY | 1,000 |
| Tomato___healthy | NORMAL | 1,590 |
| Tomato___Late_blight | ANOMALY | 1,909 |
| Tomato___Leaf_Mold | ANOMALY | 952 |
| Tomato___Septoria_leaf_spot | ANOMALY | 1,771 |
| Tomato___Spider_mites Two-spotted_spider_mite | ANOMALY | 1,676 |
| Tomato___Target_Spot | ANOMALY | 1,404 |
| Tomato___Tomato_mosaic_virus | ANOMALY | 373 |
| Tomato___Tomato_Yellow_Leaf_Curl_Virus | ANOMALY | 5,357 |
| **Accepted total** | **15,079 NORMAL / 39,221 ANOMALY** | **54,300** |

## Measured AGM-030 run

The complete pinned archive was subsequently retrieved and audited. Its SHA-256
is `ae430d573bda45084545c84d5ca54a830d932962e80f385396956d799d1f254e`.
The audit accepted 54,300 images, excluded the five rejected images, and found
no unreadable, unsupported, unknown, or conflicting-label files. It found 21
exact-duplicate groups and 441 dHash near-duplicate candidate pairs. The dataset
fingerprint is `63369aa85d39b8bb534319b480ea825ee07ad3642239b3fbf3ab7d62376d6174`.

The seed-42 split contains 38,011 train, 8,144 validation, and 8,145 untouched
test images. No exact-duplicate group crosses partitions. Of the coarse dHash
candidates, 215 cross partitions; 38 candidate pairs cross labels, demonstrating
why these candidates are not treated as trustworthy biological leaf identity.
The split fingerprint is
`a275945b57f4a22dba7a9cb5044a13b2d77d820775ce8551cadc000f115a3905`.

Validation-only results were 0.719917 accuracy / 0.684018 macro-F1 for the
mean-RGB baseline and 0.980108 accuracy / 0.975570 macro-F1 for MobileNetV2.
Training stopped after epoch 6 with patience 3 and restored epoch 3. The held-out
test partition was not evaluated. The selected state dictionary is stored at
`ai/computer_vision/artifacts/agm-030-mobilenet-v2.pt` with SHA-256
`8ec201b6cedec833c90705cd0067782e690c80d176e03b6d38eaec498c74c9f8`;
its adjacent metadata records the dataset, split, preprocessing, runtime,
configuration, and validation evidence.

## Scientific limitation

The mirror does not expose trustworthy physical-leaf grouping. Exact duplicates
are kept together, but related photographs could still cross splits.
PlantVillage predominantly contains controlled single-leaf photographs. Any
validation result measures that domain only; it does not establish field,
smartphone, Morus alba, Tunisian-farm, unseen-species, or diagnostic performance.
