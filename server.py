from flask import Flask, jsonify
from flask_restx import Api, Resource, reqparse
from flask_jwt_extended import jwt_optional, get_jwt_identity

from qwc_services_core.api import CaseInsensitiveArgument
from qwc_services_core.app import app_nocache
from qwc_services_core.jwt import jwt_manager
from qwc_services_core.tenant_handler import TenantHandler
from legend_service import LegendService


# Flask application
app = Flask(__name__)
app_nocache(app)
api = Api(app, version='1.0', title='Legend service API',
          description="""API for QWC Legend service.

The legend service delivers layer legends using an API based on
WMS GetLegendGraphic.
          """,
          default_label='Legend operations', doc='/api/')

# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

# Setup the Flask-JWT-Extended extension
jwt = jwt_manager(app)

# create tenant handler
tenant_handler = TenantHandler(app.logger)


def legend_service_handler():
    """Get or create a LegendService instance for a tenant."""
    tenant = tenant_handler.tenant()
    handler = tenant_handler.handler('legend', 'legend', tenant)
    if handler is None:
        handler = tenant_handler.register_handler(
            'legend', tenant, LegendService(tenant, app.logger))
    return handler


# request parser
legend_parser = reqparse.RequestParser(argument_class=CaseInsensitiveArgument)
legend_parser.add_argument('layer', required=True)
legend_parser.add_argument('format')
legend_parser.add_argument('bbox')
legend_parser.add_argument('crs')
legend_parser.add_argument('scale')
legend_parser.add_argument('width')
legend_parser.add_argument('height')
legend_parser.add_argument('dpi')
legend_parser.add_argument('boxspace')
legend_parser.add_argument('layerspace')
legend_parser.add_argument('layertitlespace')
legend_parser.add_argument('symbolspace')
legend_parser.add_argument('iconlabelspace')
legend_parser.add_argument('symbolwidth')
legend_parser.add_argument('symbolheight')
legend_parser.add_argument('layerfontfamily')
legend_parser.add_argument('itemfontfamily')
legend_parser.add_argument('layerfontbold')
legend_parser.add_argument('itemfontbold')
legend_parser.add_argument('layerfontsize')
legend_parser.add_argument('itemfontsize')
legend_parser.add_argument('layerfontitalic')
legend_parser.add_argument('itemfontitalic')
legend_parser.add_argument('layerfontcolor')
legend_parser.add_argument('itemfontcolor')
legend_parser.add_argument('layertitle')
legend_parser.add_argument('rulelabel')
legend_parser.add_argument('transparent')
legend_parser.add_argument('type')


# routes
@api.route('/<path:service_name>')
@api.param('service_name', 'Service name corresponding to WMS, e.g. `qwc_demo`')
class Legend(Resource):
    @api.doc('legend')
    @api.param('layer', 'The layer name')
    @api.param('format', 'The image format', default='image/png')
    @api.param('bbox', 'The extent to consider for generating the legend')
    @api.param('crs', 'The CRS of the specified extent')
    @api.param('scale', 'The scale to consider for generating the legend')
    @api.param('width', 'The map width')
    @api.param('height', 'The map height')
    @api.param('dpi', 'DPI')
    @api.param('boxspace', 'Space between legend frame and content (mm)')
    @api.param('layerspace', 'Vertical space between layers (mm)')
    @api.param('layertitlespace', 'Vertical space between layer title and items following (mm)')
    @api.param('symbolspace', 'Vertical space between symbol and item following (mm)')
    @api.param('iconlabelspace', 'Horizontal space between symbol and label text (mm)')
    @api.param('symbolwidth', 'Width of the symbol preview (mm)')
    @api.param('symbolheight', 'Height of the symbol preview (mm)')
    @api.param('layerfontfamily', 'Font family for layer title text')
    @api.param('itemfontfamily', 'Font family for layer item text')
    @api.param('layerfontbold', 'Font weight for layer title text')
    @api.param('itemfontbold', 'Font weight for layer item text')
    @api.param('layerfontsize', 'Font size in points for layer title text')
    @api.param('itemfontsize', 'Font size in points for layer item text')
    @api.param('layerfontitalic', 'Font style for layer title text')
    @api.param('itemfontitalic', 'Font style for layer item text')
    @api.param('layerfontcolor', 'Font color for layer title text')
    @api.param('itemfontcolor', 'Font color for layer item text')
    @api.param('layertitle', 'Whether to display layer title text')
    @api.param('rulelabel', 'Whether to display layer item text')
    @api.param('transparent', 'Whether to set background transparency')
    @api.param('type', 'The legend image type, either "thumbnail", or "default". Defaults to "default".')
    @api.expect(legend_parser)
    @jwt_optional
    def get(self, service_name):
        """Get legend graphic

        Return legend graphic for specified layer
        """
        args = legend_parser.parse_args()
        layer_param = args['layer'] or ''
        format_param = args['format'] or 'image/png'
        type = (args['type'] or 'default').lower()
        params = {
            "bbox": args['bbox'] or '',
            "crs": args['crs'] or '',
            "scale": args['scale'] or '',
            "width": args['width'] or '',
            "height": args['height'] or '',
            "dpi": args['dpi'] or '',
            "boxspace": args['boxspace'] or '',
            "layerspace": args['layerspace'] or '',
            "layertitlespace": args['layertitlespace'] or '',
            "symbolspace": args['symbolspace'] or '',
            "iconlabelspace": args['iconlabelspace'] or '',
            "symbolwidth": args['symbolwidth'] or '',
            "symbolheight": args['symbolheight'] or '',
            "layerfontfamily": args['layerfontfamily'] or '',
            "itemfontfamily": args['itemfontfamily'] or '',
            "layerfontbold": args['layerfontbold'] or '',
            "itemfontbold": args['itemfontbold'] or '',
            "layerfontsize": args['layerfontsize'] or '',
            "itemfontsize": args['itemfontsize'] or '',
            "layerfontitalic": args['layerfontitalic'] or '',
            "itemfontitalic": args['itemfontitalic'] or '',
            "layerfontcolor": args['layerfontcolor'] or '',
            "itemfontcolor": args['itemfontcolor'] or '',
            "layertitle": args['layertitle'] or '',
            "transparent": args['transparent'] or '',
            "rulelabel": args['rulelabel'] or ''
        }
        # Filter empty params
        params = {k: v for k, v in params.items() if v}

        legend_service = legend_service_handler()
        return legend_service.get_legend(
            service_name, layer_param, format_param, params, type,
            get_jwt_identity()
        )


""" readyness probe endpoint """
@app.route("/ready", methods=['GET'])
def ready():
    return jsonify({"status": "OK"})


""" liveness probe endpoint """
@app.route("/healthz", methods=['GET'])
def healthz():
    return jsonify({"status": "OK"})


# local webserver
if __name__ == '__main__':
    print("Starting GetLegend service...")
    from flask_cors import CORS
    CORS(app)
    app.run(host='localhost', port=5014, debug=True)
