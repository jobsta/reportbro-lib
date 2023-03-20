import importlib.resources

def test_resources_waterpark_present():
	with importlib.resources.path('reportbro.data', 'logo_watermark.png') as p:
		watermark_filename = p
		assert(watermark_filename.exists())
