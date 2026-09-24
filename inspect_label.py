import rasterio
import numpy as np

with rasterio.open("bck/tests/fixtures/Bolivia_103757_LabelHand.tif") as src:
    label = src.read(1)
    print("shape:", label.shape)
    print("dtype:", label.dtype)
    print("unique values:", np.unique(label))
    print("nodata (from file metadata):", src.nodata)

with rasterio.open("bck/tests/fixtures/Bolivia_103757_S1Hand.tif") as src:
    print("S1 shape:", src.read(1).shape)
