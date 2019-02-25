from flask import Flask
from flask_restplus import Api, Resource, reqparse
from flask_jwt_extended import jwt_optional, get_jwt_identity, create_access_token

from qwc_services_core.api import CaseInsensitiveArgument
from qwc_services_core.jwt import jwt_manager
from legend_service import LegendService


# Flask application
app = Flask(__name__)
api = Api(app, version='1.0', title='GetLegend API',
          description='API for QWC GetLegend service',
          default_label='Legend operations', doc='/api/')

# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

# Setup the Flask-JWT-Extended extension
jwt = jwt_manager(app)

# create Legend service
legend_service = LegendService(app.logger)

# request parser
legend_parser = reqparse.RequestParser(argument_class=CaseInsensitiveArgument)
legend_parser.add_argument('layer', required=True)
legend_parser.add_argument('format')
legend_parser.add_argument('bbox')
legend_parser.add_argument('crs')
legend_parser.add_argument('scale')
legend_parser.add_argument('width')
legend_parser.add_argument('height')
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
legend_parser.add_argument('type')



# routes
@api.route('/<mapid>')
@api.param('mapid', 'The WMS service map name')
class Legend(Resource):
    @api.doc('legend')
    @api.param('layer', 'The layer name')
    @api.param('format', 'The image format', default='image/png')
    @api.param('bbox', 'The extent to consider for generating the legend')
    @api.param('crs', 'The CRS of the specified extent')
    @api.param('scale', 'The scale to consider for generating the legend')
    @api.param('width', 'The map width')
    @api.param('height', 'The map height')
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
    @api.param('type', 'The legend image type, either "thumbnail", or "default". Defaults to "default".')
    @api.expect(legend_parser)
    @jwt_optional
    def get(self, mapid):
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
            "rulelabel": args['rulelabel'] or ''
        }
        # Filter empty params
        params = {k: v for k, v in params.items() if v}

        access_token = create_access_token(get_jwt_identity())
        return legend_service.get_legend(
            mapid, layer_param, format_param, params, type, access_token
        )


# local webserver
if __name__ == '__main__':
    print("Starting GetLegend service...")
    from flask_cors import CORS
    CORS(app)
    app.run(host='localhost', port=5014, debug=True)
