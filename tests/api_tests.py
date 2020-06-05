import os
from io import BytesIO
import unittest
from urllib.parse import urlparse, parse_qs, unquote, urlencode
from PIL import Image

from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

import server


class ApiTestCase(unittest.TestCase):
    """Test case for server API"""

    def setUp(self):
        server.app.testing = True
        self.app = FlaskClient(server.app, Response)
        JWTManager(server.app)

    def tearDown(self):
        pass

    def jwtHeader(self):
        with server.app.test_request_context():
            access_token = create_access_token('test')
        return {'Authorization': 'Bearer {}'.format(access_token)}

    def test_default_legendgraphic(self):
        params = {
            'service': 'WMS',
            'version': '1.3.0',
            'request': 'GetLegendGraphic',
            'format': 'image/png',
            'layer': 'test_poly',
            'crs': 'EPSG%3A2056',
            'dpi': '96',
            'width': '64',
            'height': '64',
            'bbox': '2606082.333333333%2C1233466.3333333333%2C2633175.666666666%2C1245234.9999999998',
        }
        response = self.app.get('/somap?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")
        data = json.loads(response.data)
        self.assertEqual('somap', data['path'], 'Print project name mismatch')
        self.assertEqual('GET', data['method'], 'Method mismatch')
        get_params = data['params']
        for param in params.keys():
            self.assertTrue(param in get_params, "Parameter %s missing in response" % param)
            self.assertEqual(get_params[param], str(params[param]), "Parameter %s mismatch" % param)

    def test_custom_legendgraphic(self):
        # NOTE: test_points has a custom legend graphic image, the response is the actual image, and not the response of the dummy qgis server
        params = {
            'service': 'WMS',
            'version': '1.3.0',
            'request': 'GetLegendGraphic',
            'format': 'image/png',
            'layer': 'test_points',
            'crs': 'EPSG%3A2056',
            'dpi': '96',
            'width': '64',
            'height': '64',
            'bbox': '2606082.333333333%2C1233466.3333333333%2C2633175.666666666%2C1245234.9999999998',
        }
        response = self.app.get('/somap?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")

        success = False
        try:
            img = Image.open(BytesIO(response.data))
            success = True
        except Exception as e:
            print(e)
            success = False
        self.assertTrue(success, "Response is not a valid image")
