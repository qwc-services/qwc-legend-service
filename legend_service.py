from io import BytesIO
import os

from PIL import Image
from flask import Response, send_file
import requests

from qwc_services_core.cache import Cache


OGC_SERVER_URL = os.environ.get('OGC_SERVICE_URL', 'http://localhost:5013/')
QWC2_PATH = os.environ.get('QWC2_PATH', 'qwc2/')

PIL_Formats = {
    "image/bmp": "BMP",
    "application/postscript": "EPS",
    "image/gif": "GIF",
    "image/jpeg": "JPEG",
    "image/jp2": "JPEG 2000",
    "image/x-pcx": "PCX",
    "image/png": "PNG",
    "image/tiff": "TIFF",
    "image/webp": "WebP"
}


class LegendService:
    """LegendService class

    Provide legend graphics for WMS layers with custom legend images.
    Acts as a proxy to a QGIS server.
    """

    def __init__(self, logger):
        """Constructor

        :param Logger logger: Application logger
        """
        self.logger = logger
        self.layer_legend_images = Cache()

    def get_legend(self, mapid, layer_param, format_param, params):
        """Return legend graphic for specified layer.

        :param str mapid: WMS service name
        :param str layer_param: WMS layer names
        :param str format_param: Image format
        :param dict params: Other params to forward to QGIS Server
        """
        if format_param not in PIL_Formats:
            self.logger.warning(
                "Unsupported format requested, falling back to image/png"
            )
            format_param = "image/png"


        imgdata = []
        for layer in layer_param.split(","):
            legend_image = self.get_legend_image(mapid, layer)
            if legend_image:
                imgdata.append({"data": BytesIO(legend_image), "format": None})
            else:
                req_params = {
                    "service": "WMS",
                    "version": "1.3.0",
                    "request": "GetLegendGraphic",
                    "layer": layer,
                    "format": format_param,
                    "style": "default"
                }
                req_params.update(params)
                response = requests.get(
                    OGC_SERVER_URL.rstrip("/") + "/" + mapid, params=req_params,
                    timeout=10
                )
                self.logger.debug("Forwarding request to %s" % response.url)

                if response.content.startswith(b'<ServiceExceptionReport'):
                    self.logger.warning(response.content)
                elif response.status_code == 200:
                    buf = BytesIO()
                    buf.write(response.content)
                    imgdata.append({"data": buf, "format": format_param})
                else:
                    # Empty image in case of server error
                    output = BytesIO()
                    Image.new("RGB", (1, 1), (255, 255, 255)).save(
                        output, PIL_Formats[format_param]
                    )
                    imgdata.append({"data": output, "format": format_param})

        if len(imgdata) == 0:
            # layer not found or faulty
            return Response(
                (
                    '<ServiceExceptionReport version="1.3.0">\n'
                    ' <ServiceException code="LayerNotDefined">'
                    'Layer "%s" does not exist'
                    '</ServiceException>\n'
                    '</ServiceExceptionReport>' % layer_param
                ),
                content_type='text/xml; charset=utf-8',
                status=200
            )
        # If just one image, return it
        elif len(imgdata) == 1:
            # Convert to requested format if necessary
            if imgdata[0]["format"] != format_param:
                output = BytesIO()
                try:
                    imgdata[0]["data"].seek(0)
                    Image.open(imgdata[0]["data"]).save(
                        output, PIL_Formats[format_param]
                    )
                except:
                    # Empty 1x1 image
                    Image.new("RGB", (1, 1), (255, 255, 255)).save(
                        output, PIL_Formats[format_param]
                    )
                output.seek(0)
                imgdata[0]["data"] = output

            imgdata[0]["data"].seek(0)
            return send_file(imgdata[0]["data"], mimetype=format_param)

        # Otherwise, compose images
        width = 0
        height = 0
        for entry in imgdata:
            try:
                entry["image"] = Image.open(entry["data"])
                width = max(width, entry["image"].width)
                height += entry["image"].height
            except:
                entry["image"] = None

        image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        y = 0
        for entry in imgdata:
            if entry["image"]:
                image.paste(entry["image"], (0, y))
                y += entry["image"].height

        data = BytesIO()
        image.save(data, PIL_Formats[format_param])
        data.seek(0)
        return send_file(data, mimetype=format_param)

    def get_legend_image(self, mapid, layer):
        print(os.path.join(QWC2_PATH, 'assets', 'legend', mapid, layer + '.png'))
        try:
            return open(os.path.join(QWC2_PATH, 'assets', 'legend', mapid, layer + '.png'), 'rb').read()
        except:
            return None
