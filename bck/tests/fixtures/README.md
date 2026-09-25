# Test fixtures: provenance

## `levir_cd_test_102_2_{t1,t2}.jpg`, `levir_cd_test_102_2_label.png` (LEVIR-CD **test** split)

- **Source:** Hugging Face dataset `ericyu/LEVIRCD_Cropped256` at revision
  `b5a9ebf7faf7f67ce9d735a3bccde4622f351728`. This is LEVIR-CD cropped into 256×256 tiles.
- **Split:** `test`, file `data/test-00000-of-00001-31d7c3e3444e5b5d.parquet`, row 40. The
  dataset's own path is `test_102_2.jpg`, i.e. tile 2 of LEVIR-CD test image 102.
- **Bytes:** stored exactly as in the dataset (JPEG images, PNG label), not re-encoded.
  - t1 (pre, `imageA`): sha256 `c0d3f044c3e14b6e906f4ea404dbb5fb610ec34ac2f67995ecb143a8d9aee91d`
  - t2 (post, `imageB`): sha256 `98236dfbf92fac76bd41745bc4a5fba896b4ab7eaf06257d14aed1e665b73b29`
  - label: sha256 `a4223b16cda4fda2bda583e4232603ad91a8700676d1a977401851fb746818ff`
- **Why this pair:** it is the demo pair for the change_detection → VQA sequence. All 2,048
  test-split pairs were run through local BIT and the real confounder gate:
  - 283 were rejected by registration quality, 1,195 suppressed by the 2% gate, and 570 passed.
  - 315 passed with a largest connected component of at least 2% of the frame on its own.
  - Ranked by IoU with the ground-truth label, this pair is second: BIT change 20.91%,
    ground truth 20.68%, IoU 0.974.
  - The first-ranked pair (`test_16_4`, 68% change) covers most of the frame, so its crop would be
    nearly the whole image.
  - Here the largest component is 13,704 px (20.91%), bbox [79, 0, 256, 176], which becomes a
    177×176 handoff crop.
  - Pinned by `tests/pipeline/test_levir_test_split_demo_pair.py`.

## Other LEVIR-CD tiles
- `levir_test_1_*`: pixel-identical to row 0 of the same dataset's `test` split. BIT finds 0%
  change there (a true no-change pair), so the gate suppresses it.
- `levir_train_103_9_*`: **training** split. It is not used for the composite demo.
