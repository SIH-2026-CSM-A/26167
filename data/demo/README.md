# SatQuery AI curated demo dataset

This directory is the local, pre-cached imagery package for F24. Runtime paths in
`manifest.json` are POSIX paths relative to this directory. No preset requires an
external imagery fetch.

## Packaged assets

| Packaged file | Original repository fixture | Bytes | SHA-256 |
|---|---|---:|---|
| `assets/sen1floods11_bolivia_103757_s1_sar.tif` | `bck/tests/fixtures/Bolivia_103757_S1Hand.tif` | 698748 | `d7c7630e6540b3d32b063ed079d73e55c95b1c0347f5d94257b2b7300befb4c8` |
| `assets/sen1floods11_bolivia_103757_s2_optical.tif` | `bck/tests/fixtures/Bolivia_103757_S2Hand.tif` | 908533 | `d16f68d9fffa6235b44cc31b186ec4ab5179420892fc59589d597717afeb19ad` |
| `assets/levir_cd_train_103_9_before.png` | `bck/tests/fixtures/levir_train_103_9_t1.png` | 162163 | `4153eb70e037c724dbddc5886de715953aacbcd97065590cc7e2f78f72aed12c` |
| `assets/levir_cd_train_103_9_after.png` | `bck/tests/fixtures/levir_train_103_9_t2.png` | 154055 | `8d1e8ea0ed0aa4caf6fc45558546deefd359c48fe7f531944ac14758c02743d5` |

The packaged files are byte-for-byte copies of those existing fixtures. Their
hashes are recorded so future packaging changes can detect accidental conversion
or recompression.

## Provenance available in this repository

- The `Bolivia_103757` pair is from Sen1Floods11. Existing fusion tests identify
  the Sentinel-1 bands as VV/VH backscatter in dB and the co-registered
  Sentinel-2 asset as 13-band optical imagery. Repository tests validate water
  extraction against the corresponding hand label, which is deliberately not
  copied into this runtime package.
- The `train_103_9` pair is a real LEVIR-CD 256×256 before/after chip extracted
  from the ChangeFormer-linked preprocessed release. Existing BIT tests record a
  real built-up change for this pair. Its label is deliberately not copied into
  this runtime package.

The repository evidence inspected for JASH-005 does not establish a specific
license statement for these copied fixture files, so this package does not make
one. No replacement imagery was downloaded for this ticket.
