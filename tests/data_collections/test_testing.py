from datetime import datetime

import geopyspark
import numpy as np
from numpy.testing import assert_equal

from openeogeotrellis.collections.testing import (
    GeopysparkCubeMetadata,
    TestCollectionLonLat,
    load_test_collection,
)
from openeogeotrellis.geopysparkdatacube import GeopysparkDataCube
from openeogeotrellis.utils import get_jvm


def test_test_collection():
    date = datetime(2021, 4, 26)
    builder = TestCollectionLonLat(tile_size=4, grid_size=1.0, tile_origin=(1, 7))
    assert_equal(builder.get_band_tile("Flat:0", 1, 2, date), np.zeros((4, 4)))
    assert_equal(builder.get_band_tile("Flat:1", 1, 2, date), np.ones((4, 4)))
    assert_equal(builder.get_band_tile("Flat:2", 1, 2, date), np.full((4, 4), 2))
    assert_equal(builder.get_band_tile("TileCol", 3, 5, date), np.full((4, 4), 3))
    assert_equal(builder.get_band_tile("TileRow", 3, 5, date), np.full((4, 4), 5))
    assert_equal(builder.get_band_tile("TileColRow", 3, 5, date), np.full((4, 4), 35))
    assert_equal(
        builder.get_band_tile("TileColRow:100", 3, 5, date),
        np.full((4, 4), 305),
    )
    assert_equal(
        builder.get_band_tile("Longitude", 3, 5, date),
        np.array([[4, 4.25, 4.5, 4.75]] * 4),
    )
    assert_equal(
        builder.get_band_tile("Latitude", 3, 5, date),
        np.array(
            [
                [1.75, 1.75, 1.75, 1.75],
                [1.50, 1.50, 1.50, 1.50],
                [1.25, 1.25, 1.25, 1.25],
                [1.00, 1.00, 1.00, 1.00],
            ]
        ),
    )
    assert_equal(builder.get_band_tile("Year", 3, 5, date), np.full((4, 4), 2021))
    assert_equal(builder.get_band_tile("Month", 3, 5, date), np.full((4, 4), 4))
    assert_equal(builder.get_band_tile("Day", 3, 5, date), np.full((4, 4), 26))


def test_load_test_collection():
    bands = ["Flat:1", "TileCol", "TileRow", "Longitude", "Latitude", "Day"]
    collection_metadata = GeopysparkCubeMetadata({"cube:dimensions": {
        "x": {"type": "spatial", "axis": "x"},
        "y": {"type": "spatial", "axis": "y"},
        "t": {"type": "temporal"},
        "bands": {"type": "bands", "values": bands}
    }})

    extent = get_jvm().geotrellis.vector.Extent(1.0, 2.0, 2.0, 4.0)
    pyramid = load_test_collection(
        tile_size=4,
        collection_metadata=collection_metadata,
        extent=extent,
        srs="EPSG:4326",
        from_date="2021-01-20",
        to_date="2021-01-30",
        bands=bands
    )
    cube = GeopysparkDataCube(
        pyramid=geopyspark.Pyramid(pyramid),
        metadata=collection_metadata
    )

    data = cube.pyramid.levels[0].to_spatial_layer().stitch()
    print(data)

    assert data.cells.shape == (6, 8, 4)
    assert_equal(data.cells[0], np.ones((8, 4)))
    assert_equal(data.cells[1], [[0, 0, 0, 0]] * 8)
    assert_equal(data.cells[2], [[0, 0, 0, 0]] * 4 + [[1, 1, 1, 1]] * 4)
    assert_equal(data.cells[3], [[1.0, 1.25, 1.5, 1.75]] * 8)
    assert_equal(
        data.cells[4],
        np.array(([[3.75, 3.5, 3.25, 3.0, 2.75, 2.5, 2.25, 2]] * 4)).T,
    )
    assert_equal(data.cells[5], 25.0 * np.ones((8, 4)))
