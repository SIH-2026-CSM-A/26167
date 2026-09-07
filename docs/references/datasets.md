# Dataset Reference Sheet

## BigEarthNet.txt

**Source (VERIFIED):** arxiv.org/abs/2603.29630

- 464,044 co-registered Sentinel-1 SAR / Sentinel-2 multispectral image pairs
- Built on the refined BigEarthNet (reBEN) base
- 9.6M text annotations already included: geographically-anchored captions,
  binary yes/no VQA, multiple-choice VQA, and referring-expression detections
  (bounding boxes)
- Manually-verified benchmark split: 1,082 image pairs — 970 captions, 6,927
  binary VQA, 5,550 MCQ VQA, 1,582 referring-expression annotations
- The dataset's own authors used InternVL as their adaptation baseline on
  this exact data

## SEN12MS

**Sources (VERIFIED):**
- TU Munich — supplementary training data
- Schmitt et al., "SEN12MS -- A Curated Dataset of Georeferenced
  Multi-Spectral Sentinel-1/2 Imagery for Deep Learning and Data Fusion"
  (arXiv:1906.07789 / DLR preprint elib.dlr.de/133280)

- 180,662 Sentinel-1 / Sentinel-2 / MODIS triplets
- Used for supplementary SAR-optical fusion training, not a PS-named
  requirement
- Sentinel-1 SAR channels (VV, VH) are already provided as calibrated
  sigma-nought (σ0) backscatter in dB scale, at 5m (azimuth) × 20m (range)
  pixel spacing — **not raw digital numbers.** No raw DN exists in this
  dataset to calibrate from.
- The dataset's own authors explicitly state they leave further processing
  (e.g. speckle filtering) to the end user and do not apply it themselves.

> [!IMPORTANT]
> **Known pitfall, already hit once:** this is the exact mistake ROHAN-001
> made and was corrected for — attempting to calibrate SEN12MS SAR data from
> an assumed-raw DN when it was already in dB. Documented here so it isn't
> repeated.

## LEVIR-CD

**Source (VERIFIED):** https://justchenhao.github.io/LEVIR/

- 637 bitemporal 1024×1024px patch pairs
- 0.5m/pixel ground sample distance (GSD)
- Google Earth imagery
- 5–14 years between each pair's two acquisitions
- 20 regions across Texas cities
- Capture range: 2002–2018
- 31,333 building-change instances
- Binary building-growth/decline labels
- Train/val/test split sizes: **not verified** — not stated in the cited
  source page as reviewed for this document; not guessed.

## Sen1Floods11

**Source (VERIFIED):** Bonafilia et al. 2020, CVPRW —
https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/Bonafilia_Sen1Floods11...

- Primary sensor: Sentinel-1 SAR
- Sentinel-2 and Landsat used for label generation (not primary imagery)
- 446 hand-labeled flood chips
- 814 JRC permanent-water chips
- 4,385 Sentinel-2-classified chips
- 4,385 Sentinel-1-classified chips
- 4,831 chips total
- 512×512px chip size
- 120,406 km² total coverage
- 14 biomes / 357 ecoregions / 6 continents
- 11 flood events
- Three label classes: permanent water, flood water, total surface water
