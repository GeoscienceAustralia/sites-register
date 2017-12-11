from datetime import datetime
from io import StringIO
import requests
from flask import Response, render_template
from lxml import etree
from lxml import objectify
from rdflib import Graph, URIRef, RDF, RDFS, XSD, OWL, Namespace, Literal, BNode
import _config as conf
from _ldapi.__init__ import LDAPI
from datetime import datetime
import json


class Site:

    URI_GA = 'http://pid.geoscience.gov.au/org/ga/geoscienceausralia'

    def __init__(self, site_no, xml=None):
        self.site_no = None
        self.site_type = None
        self.status = None

        if xml is not None:  # even if there are values for Oracle API URI and IGSN, load from XML file if present
            self._populate_from_xml_file(xml)
        else:
            self._populate_from_oracle_api()

    def validate_xml(self, xml):
        parser = etree.XMLParser(dtd_validation=False)

        try:
            etree.fromstring(xml, parser)
            return True
        except Exception:
            print('not valid xml')
            return False

    def _populate_from_oracle_api(self):
        """
        Populates this instance with data from the Oracle Samples table API

        :param oracle_api_samples_url: the Oracle XML API URL string for a single sample
        :param igsn: the IGSN of the sample desired
        :return: None
        """
        # internal URI
        # os.environ['NO_PROXY'] = 'ga.gov.au'
        # call API
        r = requests.get(_config.XML_API_URL_SITE.format(self.igsn))
        if "No data" in r.content.decode('utf-8'):
            raise ParameterError('No Data')

        if self.validate_xml(r.content):
            self._populate_from_xml_file(r.content)
            return True
        else:
            return False

    def _populate_from_xml_file(self, xml):
        """
        Populates this instance with data from an XML file.

        :param xml: XML according to GA's Oracle XML API from the Samples DB
        :return: None
        """
        try:
            root = objectify.fromstring(xml)

            self.igsn = root.ROW.IGSN
            if hasattr(root.ROW, 'SAMPLEID'):
                self.sample_id = root.ROW.SAMPLEID
            self.sample_no = root.ROW.SAMPLENO
            self.access_rights = self._make_vocab_uri('public', 'access_rights')  # this value is statically set to 'public' for all samples
            if hasattr(root.ROW, 'REMARK'):
                self.remark = str(root.ROW.REMARK).strip() if len(str(root.ROW.REMARK)) > 5 else None
            if hasattr(root.ROW, 'SAMPLE_TYPE_NEW'):
                self.sample_type = self._make_vocab_uri(root.ROW.SAMPLE_TYPE_NEW, 'sample_type')
            if hasattr(root.ROW, 'SAMPLING_METHOD'):
                self.method_type = self._make_vocab_uri(root.ROW.SAMPLING_METHOD, 'method_type')
            if hasattr(root.ROW, 'MATERIAL_CLASS'):
                self.material_type = self._make_vocab_uri(root.ROW.MATERIAL_CLASS, 'material_type')
            # self.long_min = root.ROW.SAMPLE_MIN_LONGITUDE
            # self.long_max = root.ROW.SAMPLE_MAX_LONGITUDE
            # self.lat_min = root.ROW.SAMPLE_MIN_LATITUDE
            # self.lat_max = root.ROW.SAMPLE_MAX_LATITUDE
            if hasattr(root.ROW, 'SDO_GTYPE'):
                self.gtype = root.ROW.GEOM.SDO_GTYPE

            self.srid = 'GDA94'  # if root.ROW.GEOM.SDO_SRID == '8311' else root.ROW.GEOM.SDO_SRID

            if hasattr(root.ROW, 'GEOM'):
                if hasattr(root.ROW.GEOM, 'SDO_POINT'):
                    if hasattr(root.ROW.GEOM.SDO_POINT, 'X'):
                        self.x = root.ROW.GEOM.SDO_POINT.X
                    if hasattr(root.ROW.GEOM.SDO_POINT, 'Y'):
                        self.y = root.ROW.GEOM.SDO_POINT.Y
                    if hasattr(root.ROW.GEOM.SDO_POINT, 'Z'):
                        self.z = root.ROW.GEOM.SDO_POINT.Z
                if hasattr(root.ROW.GEOM, 'SDO_ELEM_INFO'):
                    self.elem_info = root.ROW.GEOM.SDO_ELEM_INFO
                if hasattr(root.ROW, 'SDO_ORDINATES'):
                    self.ordinates = root.ROW.GEOM.SDO_ORDINATES
            if hasattr(root.ROW, 'STATEID'):
                self.state = root.ROW.STATEID  # self._make_vocab_uri(root.ROW.STATEID, 'state')
            if hasattr(root.ROW, 'COUNTRY'):
                self.country = root.ROW.COUNTRY
            if hasattr(root.ROW, 'TOP_DEPTH'):
                self.depth_top = root.ROW.TOP_DEPTH
            if hasattr(root.ROW, 'BASE_DEPTH'):
                self.depth_base = root.ROW.BASE_DEPTH
            if hasattr(root.ROW, 'STRATNAME'):
                self.strath = root.ROW.STRATNAME
            if hasattr(root.ROW, 'AGE'):
                self.age = root.ROW.AGE
            if hasattr(root.ROW, 'LITHNAME'):
                self.lith = self._make_vocab_uri(root.ROW.LITHNAME, 'lithology')
            if hasattr(root.ROW, 'ACQUIREDATE'):
                self.date_acquired = str2datetime(root.ROW.ACQUIREDATE).date()
            if hasattr(root.ROW, 'MODIFIED_DATE'):
                self.date_modified = str2datetime(root.ROW.MODIFIED_DATE)
            if hasattr(root.ROW, 'ENO'):
                self.entity_uri = 'http://pid.geoscience.gov.au/site/' + str(root.ROW.ENO)
            if hasattr(root.ROW, 'ENTITYID'):
                self.entity_name = root.ROW.ENTITYID
            if hasattr(root.ROW, 'ENTITYID'):
                self.entity_type = self._make_vocab_uri(root.ROW.ENTITY_TYPE, 'entity_type')
            if hasattr(root.ROW, 'HOLE_MIN_LONGITUDE'):
                self.hole_long_min = root.ROW.HOLE_MIN_LONGITUDE
            if hasattr(root.ROW, 'HOLE_MAX_LONGITUDE'):
                self.hole_long_max = root.ROW.HOLE_MAX_LONGITUDE
            if hasattr(root.ROW, 'HOLE_MIN_LATITUDE'):
                self.hole_lat_min = root.ROW.HOLE_MIN_LATITUDE
            if hasattr(root.ROW, 'HOLE_MAX_LATITUDE'):
                self.hole_lat_max = root.ROW.HOLE_MAX_LATITUDE
            # self.date_modified = None
            # self.modified_datestamp = None
            # TODO: replace all the other calls to this with a call to self.wkt instead
            # self.wkt = self._generate_sample_wkt()
        except Exception as e:
            print(e)

        return True

    def render(self, view, mimetype):
        if self.site_no is None:
            return Response('Site {} not found.'.format(self.site_no), status=404, mimetype='text/plain')

        if view == 'pdm':
            if mimetype == 'text/html':
                return self.export_html(model_view=view)
            else:
                return Response(self.export_rdf(view, mimetype), mimetype=mimetype)
        elif view == 'dc':
            if mimetype == 'text/html':
                return self.export_html(model_view=view)
            elif mimetype == 'text/xml':
                return Response(self.export_dc_xml(), mimetype=mimetype)
            else:
                return Response(self.export_rdf(view, mimetype), mimetype=mimetype)
        elif view == 'prov':
            if mimetype == 'text/html':
                return self.export_html(model_view=view)
            else:
                return Response(self.export_rdf(view, mimetype), mimetype=mimetype)
        elif view == 'sosa':  # RDF only for this view
            return Response(self.export_rdf(view, mimetype), mimetype=mimetype)

    def export_nemsr_geojson(self):
        """
        NEII documentation for site GeoJSON properties: http://www.neii.gov.au/nemsr/documentation/1.0/data-fields/site
        :return:
        :rtype:
        """
        site = {
            'type': 'FeatureCollection',
            'properties': {
                'network': {}  # TODO: generate this in network.py and import
            },
            'features': {
                'type': 'Feature',
                'id': '{}{}'.format(conf.URI_SITE_INSTANCE_BASE, self.site_no),
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        149, -35, 21
                    ]
                },
                'crs': {
                    'type': 'link',
                    'properties': {
                        'href': 'http://www.opengis.net/def/crs/EPSG/0/4283',  # the NEII examples use WGS-84, we GDA-94
                        'type': 'proj4'  # TODO: Irina to check this
                    }
                },
                'properties': {
                    'name': '{} {}'.format('Site', self.site_no),
                    'siteDescription': self.site_type,
                    'siteLicence': 'open-CC',  # http://cloud.neii.gov.au/neii/neii-licencing/version-1/concept
                    'siteURL': '{}{}'.format(conf.URI_SITE_INSTANCE_BASE, self.site_no),
                    'operatingAuthority': {
                        'name': 'Geoscience Australia',
                        'id': Site.URI_GA
                    }
                },
                'siteStatus': self.status,
                'extensionFieldValue1': '',  # TODO: find our obligations for this and other extension values
                'extensionFieldValue2': '',
                'extensionFieldValue3': '',
                'extensionFieldValue4': '',
                'extensionFieldValue5': '',
                'observingCapabilities': {}  # TODO: generate this in observing_capabilities.py and import
            },
        }

        return Response(
            json.dumps(site),
            mimetype='pplication/vnd.geo+json'
        )

    def export_rdf(self, model_view='pdm', rdf_mime='text/turtle'):
        """
        Exports this instance in RDF, according to a given model from the list of supported models,
        in a given rdflib RDF format

        :param model_view: string of one of the model view names available for Sample objects ['igsn', 'dc', '',
            'default']
        :param rdf_mime: string of one of the rdflib serlialization format ['n3', 'nquads', 'nt', 'pretty-xml', 'trig',
            'trix', 'turtle', 'xml'], from http://rdflib3.readthedocs.io/en/latest/plugin_serializers.html
        :return: RDF string
        """

        # things that are applicable to all model views; the graph and some namespaces
        g = Graph()

        # URI for this sample
        base_uri = 'http://pid.geoscience.gov.au/site/'
        this_site = URIRef(base_uri + self.site_no)
        g.add((this_site, RDFS.label, Literal('Site ' + self.site_no, datatype=XSD.string)))

        # define GA
        ga = URIRef(Site.URI_GA)

    def export_html(self, model_view='pdm'):
        """
        Exports this instance in HTML, according to a given model from the list of supported models.

        :param model_view: string of one of the model view names available for Sample objects ['igsn', 'dc', '',
            'default']
        :return: HTML string
        """
        if model_view == 'pdm':
            view_title = 'IGSN Ontology view'
            sample_table_html = render_template(
                'class_sample_igsn-o.html',
                igsn=self.igsn,
                sample_id=self.sample_id,
                description=self.remark,
                access_rights_alink=self._make_vocab_alink(self.access_rights),
                date_acquired=self.date_acquired if self.date_acquired is not None else '<a href="{}">{}</a>'.format(Sample.URI_MISSSING, Sample.URI_MISSSING.split('/')[-1]),
                wkt=self._generate_sample_wkt(),
                state=self.state,
                sample_type_alink=self._make_vocab_alink(self.sample_type),
                method_type_alink=self._make_vocab_alink(self.method_type),
                material_type_alink=self._make_vocab_alink(self.material_type),
                lithology_alink=self._make_vocab_alink(self.lith),
                entity_type_alink=self._make_vocab_alink(self.entity_type)
            )
        elif model_view == 'prov':
            view_title = 'PROV Ontology view'
            prov_turtle = self.export_rdf('prov', 'text/turtle')
            g = Graph().parse(data=prov_turtle, format='turtle')

            sample_table_html = render_template(
                'class_sample_prov.html',
                visjs=self._make_vsjs(g),
                prov_turtle=prov_turtle,
            )
        else:  # elif model_view == 'dc':
            view_title = 'Dublin Core view'

            sample_table_html = render_template(
                'class_sample_dc.html',
                identifier=self.igsn,
                description=self.remark if self.remark != '' else '-',
                date=self.date_acquired if self.date_acquired is not None else '<a href="{}">{}</a>'.format(
                    Sample.URI_MISSSING, Sample.URI_MISSSING.split('/')[-1]),
                type=self.sample_type,
                format=self.material_type,
                wkt=self._generate_sample_wkt(),
                creator='<a href="{}">Geoscience Australia</a>'.format(Sample.URI_GA),
                publisher='<a href="{}">Geoscience Australia</a>'.format(Sample.URI_GA),
            )

        if self.date_acquired is not None:
            year_acquired = '({})'.format(datetime.strftime(self.date_acquired, '%Y'))
        else:
            year_acquired = ''

        # add in the Pingback header links as they are valid for all HTML views
        pingback_uri = conf.URI_SITE_INSTANCE_BASE + self.igsn + "/pingback"
        headers = {
            'Link': '<{}>;rel = "http://www.w3.org/ns/prov#pingback"'.format(pingback_uri)
        }

        return Response(
            render_template(
                'page_site.html',
                view=model_view,
                igsn=self.igsn,
                year_acquired=year_acquired,
                view_title=view_title,
                sample_table_html=sample_table_html,
                date_now=datetime.now().strftime('%d %B %Y'),
                gm_key=_config.GOOGLE_MAPS_API_KEY,
                lat=self.y,
                lon=self.x
            ),
            headers=headers
        )


class ParameterError(ValueError):
    pass