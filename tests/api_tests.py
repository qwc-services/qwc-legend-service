import os
from io import BytesIO
import unittest
from urllib.parse import urlparse, parse_qs, unquote, urlencode
from PIL import Image

from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

import server
JWTManager(server.app)


class ApiTestCase(unittest.TestCase):
    """Test case for server API"""

    def setUp(self):
        server.app.testing = True
        self.app = FlaskClient(server.app, Response)

    def tearDown(self):
        pass

    def jwtHeader(self):
        with server.app.test_request_context():
            access_token = create_access_token('test')
        return {'Authorization': 'Bearer {}'.format(access_token)}

    def test_default_legendgraphic(self):
        params = {
            'SERVICE': 'WMS',
            'REQUEST': 'GetLegendGraphic',
            'format': 'image/png',
            'LAYER': 'edit_polygons'
        }
        response = self.app.get('/qwc_demo?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")

        success = False
        try:
            img = Image.open(BytesIO(response.data))
            success = True
        except Exception as e:
            print(e)
            success = False
        self.assertTrue(success, "Response is not a valid image")

    def test_custom_legendgraphic(self):
        # NOTE: edit_points has a custom legend graphic image, the response is the actual image, and not the response of the dummy qgis server
        params = {
            'SERVICE': 'WMS',
            'REQUEST': 'GetLegendGraphic',
            'format': 'image/png',
            'LAYER': 'edit_points'
        }
        response = self.app.get('/qwc_demo?' + urlencode(params), headers=self.jwtHeader())
        self.assertEqual(200, response.status_code, "Status code is not OK")

        success = False
        try:
            img = Image.open(BytesIO(response.data))
            success = True
        except Exception as e:
            print(e)
            success = False
        self.assertTrue(success, "Response is not a valid image")
