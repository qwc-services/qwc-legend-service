import base64
from io import BytesIO
import os
import tempfile
import uuid

from PIL import Image
from flask import Response, send_file
import requests
from xml.sax.saxutils import escape as xml_escape

from qwc_services_core.permissions_reader import PermissionsReader
from qwc_services_core.runtime_config import RuntimeConfig


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

FORMATS_WITH_ALPHA = set([
    "image/png",
    "image/webp"
])


class LegendService:
    """LegendService class

    Provide legend graphics for WMS layers with custom legend images.
    Acts as a proxy to a QGIS server.
    """

    def __init__(self, tenant, logger):
        """Constructor

        :param Logger logger: Application logger
        """
        self.tenant = tenant
        self.logger = logger

        config_handler = RuntimeConfig("legend", logger)
        config = config_handler.tenant_config(tenant)

        # get internal QGIS server URL from config
        self.qgis_server_url = config.get(
            'default_qgis_server_url', 'http://localhost:8001/ows/'
        ).rstrip('/') + '/'

        qgis_server_url_tenant_suffix = config.get('qgis_server_url_tenant_suffix', '').strip('/')
        if qgis_server_url_tenant_suffix:
            self.qgis_server_url += qgis_server_url_tenant_suffix + '/'

        self.network_timeout = config.get('network_timeout', 30)

        self.basic_auth_login_url = config.get('basic_auth_login_url')
        self.legend_default_font_size = config.get("legend_default_font_size")

        # get path to legend images from config
        self.legend_images_path = config.get('legend_images_path', '/legends/')

        self.resources = self.load_resources(config)
        self.permissions_handler = PermissionsReader(tenant, logger)

    def get_legend(self, service_name, layers_param, styles_param, format_param, params, type,
                   identity):
        """Return legend graphic for specified layer.

        :param str service_name: Service name
        :param str layers_param: WMS layer names
        :param str styles_param: WMS layer styles
        :param str format_param: Image format
        :param dict params: Other params to forward to QGIS Server
        :param str type: The legend image type, either "default", "thumbnail" or "tooltip".
        :param obj identity: User identity
        """
        permissions = self.wms_permissions(service_name, identity)
        if not permissions:
            # map unknown or not permitted
            return self.service_exception(
                'MapNotDefined',
                'Map "%s" does not exist or is not permitted' % service_name
            )

        if format_param not in PIL_Formats:
            self.logger.warning(
                "Unsupported format requested, falling back to image/png"
            )
            format_param = "image/png"

        # get requested layers/styles
        layers = layers_param.split(',')
        styles = styles_param.split(',')
        styles.extend([''] * (len(layers) - len(styles)))
        requested_layer_styles =  [{'layer': l, 'style': s} for l, s in zip(layers, styles)]

        self.logger.debug("Requested layers: %s" % str(requested_layer_styles))

        # Collect permitted layers
        permitted_layers = set()
        for permission in permissions:
            for layer in permission['layers']:
                permitted_layers.add(layer['name'])
        self.logger.debug("Permitted layers: %s" % str(permitted_layers))
        resource_entries = self.resources['wms_services'][service_name]['layers']

        # Filter hidden layers (i.e. children of facade groups) from requested layers
        requested_layer_styles = list(filter(
            lambda entry: not resource_entries[entry['layer']]['hidden'],
            requested_layer_styles
        ))

        # Expand layers / filter restricted layers / resolve custom legend images
        expanded_layer_styles = []
        for entry in requested_layer_styles:
            self.expand_layer(entry, resource_entries, permitted_layers, expanded_layer_styles, service_name, type)

        self.logger.debug("Expanded layers: %s" % str(
            list(map(lambda e: e | {
                "custom_legend_image": "<bytes>" if e["custom_legend_image"] else None
                }, expanded_layer_styles
            ))
        ))

        dpi = params.get('dpi')
        imgdata = []
        for layer_style in expanded_layer_styles:
            custom_legend_image = layer_style['custom_legend_image']
            if custom_legend_image is not None:
                if dpi and dpi != '90':
                    try:
                        # scale image to requested DPI
                        img = Image.open(BytesIO(custom_legend_image))
                        scale = float(dpi) / 90.0
                        new_size = (
                            int(img.width * scale), int(img.height * scale)
                        )
                        img = img.resize(new_size, Image.LANCZOS)
                        output = BytesIO()
                        # NOTE: save as PNG to preserve any alpha channel
                        img.save(output, "PNG")
                        imgdata.append({"data": output, "format": None})
                    except Exception as e:
                        self.logger.error(
                            "Could not resize image for %s:\n%s" % (layer_style['layer'], e)
                        )
                        imgdata.append(
                            {"data": BytesIO(custom_legend_image), "format": None}
                        )
                else:
                    imgdata.append({
                        "data": BytesIO(custom_legend_image), "format": None
                    })
            else:
                req_params = {
                    "service": "WMS",
                    "version": "1.3.0",
                    "request": "GetLegendGraphic",
                    "layer": layer_style['layer'],
                    "format": format_param,
                    "style": layer_style['style']
                }
                req_params.update(params)
                if self.legend_default_font_size:
                    if 'layerfontsize' not in req_params:
                        req_params['layerfontsize'] = \
                            self.legend_default_font_size
                    if 'itemfontsize' not in req_params:
                        req_params['itemfontsize'] = \
                            self.legend_default_font_size
                response = requests.get(
                    self.qgis_server_url + service_name, params=req_params,
                    timeout=self.network_timeout
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
            return self.service_exception(
                'LayerNotDefined',
                'Layer "%s" does not exist or is not permitted' % layer_param
            )

        # If just one image, return it
        elif len(imgdata) == 1:
            # Convert to requested format if necessary
            if imgdata[0]["format"] != format_param:
                output = BytesIO()
                try:
                    imgdata[0]["data"].seek(0)
                    image = Image.open(imgdata[0]["data"])
                    if not self.format_has_alpha(format_param):
                        image = self.convert_img_to_rgb(image)
                    image.save(output, PIL_Formats[format_param])
                except Exception as e:
                    self.logger.error(
                        "Could not convert image to %s:\n%s"
                        % (format_param, e)
                    )
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
                if not self.format_has_alpha(format_param):
                    entry["image"] = self.convert_img_to_rgb(entry["image"])
                width = max(width, entry["image"].width)
                height += entry["image"].height
            except:
                entry["image"] = None

        if self.format_has_alpha(format_param):
            image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        else:
            image = Image.new("RGB", (width, height), (255, 255, 255))

        y = 0
        for entry in imgdata:
            if entry["image"]:
                image.paste(entry["image"], (0, y))
                y += entry["image"].height

        data = BytesIO()
        image.save(data, PIL_Formats[format_param])
        data.seek(0)
        return send_file(data, mimetype=format_param)

    def service_exception(self, code, message):
        """Create ServiceExceptionReport XML response

        :param str code: ServiceException code
        :param str message: ServiceException text
        """
        return Response(
            (
                '<ServiceExceptionReport version="1.3.0">\n'
                ' <ServiceException code="%s">%s</ServiceException>\n'
                '</ServiceExceptionReport>'
                % (code, xml_escape(message))
            ),
            content_type='text/xml; charset=utf-8',
            status=200
        )

    def expand_layer(self, requested_layer_style, resource_entries, permitted_layers, expanded_layer_styles, service_name, type):
        """ Expand the requested layer if it is a group, and resolve any custom legend images

        :param dict requested_layer_style: The requested layer
        :param dict resource_entries: The layer resource entries
        :param set permitted_layers: The permitted layers
        :param list expanded_layer_styles: The result expanded layer styles
        :param str service_name: The WMS service name
        :param str type: The legend image type
        """
        layer = requested_layer_style['layer']
        if layer not in permitted_layers:
            return False

        resource_entry = resource_entries[layer]
        if 'sublayers' in resource_entry:
            have_custom_images = False
            group_layer_styles = []
            for sublayer in resource_entry['sublayers']:

                have_custom_images |= self.expand_layer(
                    {'layer': sublayer, 'style': requested_layer_style['style']},
                     resource_entries, permitted_layers, group_layer_styles,
                     service_name, type
                )

            # NOTE: hide_sublayers: see somap#691
            if have_custom_images or resource_entry['hide_sublayers']:
                expanded_layer_styles.extend(group_layer_styles)
            else:
                requested_layer_style.update({'custom_legend_image': None})
                expanded_layer_styles.append(requested_layer_style)
            return have_custom_images
        else:
            # Resolve custom images
            custom_image = self.get_custom_image(layer, resource_entry, service_name, type, requested_layer_style['style'])
            requested_layer_style.update({'custom_legend_image': custom_image})
            expanded_layer_styles.append(requested_layer_style)
            return custom_image != None

    def get_custom_image(self, layer, resource_entry, service_name, type, style):
        """ Return the custom legend image for the specified layer, if found
            - A filename matching legend_images_path/<service_name>/<layer>_<style>_<suffix>.png
            - A filename matching legend_images_path/<service_name>/<layer>_<suffix>.png
            - A filename matching legend_images_path/<service_name>/default_<suffix>.png
            - A filename matching legend_images_path/<service_name>/<layer>_<style>.png
            - A filename matching legend_images_path/<service_name>/<layer>.png
            - A filename matching legend_images_path/<resource_entry[legend_image]>
            - A filename matching legend_images_path/<service_name>/default.png
            - As base64 in <resource_entry[legend_image_base64]>
        Where _<suffix> may be "_thumbnail" or "_tooltip".

        :param str layer: The layer name
        :param dict resource_entry: The layer resource entry
        :param str service_name: The WMS service name
        :param str type: The legend image type
        """
        # Check for image in legend_images_path
        filenames = []
        if type == "thumbnail":
            filenames.append(os.path.join(service_name, layer + "_" + style + "_thumbnail.png"))
            filenames.append(os.path.join(service_name, layer + "_thumbnail.png"))
            filenames.append("default_thumbnail.png")
        elif type == "tooltip":
            filenames.append(os.path.join(service_name, layer + "_" + style + "_tooltip.png"))
            filenames.append(os.path.join(service_name, layer + "_tooltip.png"))
            filenames.append("default_tooltip.png")
        filenames.append(os.path.join(service_name, layer + "_" + style + '.png'))
        filenames.append(os.path.join(service_name, layer + '.png'))

        if resource_entry['legend_image']:
            filenames.append(resource_entry['legend_image'])

        filenames.append('default.png')

        for filename in filenames:
            image_path = os.path.join(self.legend_images_path, filename)
            self.logger.debug(
                "Looking for legend image '%s' for layer '%s'..." % (image_path, layer)
            )
            try:
                data = open(os.path.join(self.legend_images_path, filename), 'rb').read()
            except:
                data = None
            if data:
                self.logger.debug(
                    "Loading legend image '%s' for layer '%s'" % (image_path, layer)
                )
                return data

        # Check for base64 image in resource entry
        if resource_entry['legend_image_base64']:
            self.logger.debug("Decoded base64 custom legend for layer '%s'" % (layer))
            return base64.b64decode(resource_entry['legend_image_base64'])

        self.logger.debug("No custom legend image of type '%s' found for layer '%s'" % (type, layer))
        return None

    def format_has_alpha(self, format_param):
        """Return whether image format supports alpha channel.

        :param string format_param: Image format as media type
        """
        return format_param in FORMATS_WITH_ALPHA

    def convert_img_to_rgb(self, image):
        """Return image as RGB, converting from RGBA if necessary.

        :param Image image: Input image
        """
        if image.mode == 'RGBA':
            # remove alpha channel by compositing with white background
            background = Image.new("RGBA", image.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, image).convert("RGB")

        return image

    def load_resources(self, config):
        """Load service resources from config.

        :param RuntimeConfig config: Config handler
        """
        wms_services = {}

        # Collect WMS service layers
        for wms in config.resources().get('wms_services', []):
            layers = {}
            self.collect_layers(wms['root_layer'], layers, False)
            wms_services[wms['name']] = {'layers': layers}

        return {'wms_services': wms_services}

    def collect_layers(self, layer, layers, hidden):
        """Recursively collect layer info for layer subtree from config.

        :param obj layer: Layer or group layer
        :param obj layers: Collected layers
        :param bool hidden: Whether layer is a hidden sublayer
        """

        if layer.get('layers'):
            # group
            layers[layer['name']] = {
                'sublayers': [],
                'hidden': hidden,
                'hide_sublayers': layer.get('hide_sublayers', False)
            }
            hidden |= layer.get('hide_sublayers', False)
            for sublayer in layer['layers']:
                self.collect_layers(sublayer, layers, hidden)
                # If there are colliding group/layer names, the group entry may have been overwritten by a layer entry
                # in the nested collect_layers call
                if 'sublayer' in layers[layer['name']]:
                    layers[layer['name']]['sublayers'].append(sublayer['name'])

        else:
            layers[layer['name']] = {
                'hidden': hidden,
                'legend_image': layer.get('legend_image', None),
                'legend_image_base64': layer.get('legend_image_base64', None)
            }

    def wms_permissions(self, service_name, identity):
        """Return WMS permissions, if service is available and permitted.

        :param str service_name: Service name
        :param obj identity: User identity
        """
        if self.resources['wms_services'].get(service_name):
            # get permissions for WMS
            return self.permissions_handler.resource_permissions(
                'wms_services', identity, service_name
            )

        return None
