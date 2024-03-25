import importlib.resources

def test_resources_waterpark_present():
    WATERMARK='logo_watermark.png'
    PACKAGE='reportbro.data'

    if hasattr(importlib.resources, "as_file"):  # Python 3.9+
        from importlib.resources import as_file, files
        with as_file(files(PACKAGE).joinpath(WATERMARK)) as p:
            assert(p.exists())
    else:
        with importlib.resources.path(PACKAGE, WATERMARK) as p:
            watermark_filename = p
            assert(watermark_filename.exists())
