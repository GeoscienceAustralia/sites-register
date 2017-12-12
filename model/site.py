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
json.encoder.FLOAT_REPR = lambda f: ("%.2f" % f)


class Site:

    URI_GA = 'http://pid.geoscience.gov.au/org/ga/geoscienceausralia'

    def __init__(self, site_no, xml=None):
        self.site_no = site_no
        self.site_type = None
        self.site_description = None
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

    def _make_vocab_uri(self, xml_value, vocab_type):
        from model.lookups import TERM_LOOKUP
        if TERM_LOOKUP[vocab_type].get(xml_value) is not None:
            return TERM_LOOKUP[vocab_type].get(xml_value)
        else:
            return TERM_LOOKUP[vocab_type].get('unknown')

    def _populate_from_oracle_api(self):
        """
        Populates this instance with data from the Oracle Sites table API

        :param eno: (from class) the Entity Number of the Site desired
        :return: None
        """
        # internal URI
        # os.environ['NO_PROXY'] = 'ga.gov.au'
        # call API
        r = requests.get(conf.XML_API_URL_SITE.format(self.site_no))
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

            if hasattr(root.ROW, 'ENTITYID'):
                self.entity_id = str(root.ROW.ENTITYID)
            if hasattr(root.ROW, 'ENTITY_TYPE'):
                self.entity_type = self._make_vocab_uri(root.ROW.ENTITY_TYPE, 'entity_type')
                self.site_description = '{} ({})'.format(str(root.ROW.ENTITY_TYPE), self.entity_type)
            if hasattr(root.ROW, 'GEOM'):
                if hasattr(root.ROW.GEOM, 'SDO_POINT'):
                    if hasattr(root.ROW.GEOM.SDO_POINT, 'X'):
                        self.x = float(root.ROW.GEOM.SDO_POINT.X)
                    if hasattr(root.ROW.GEOM.SDO_POINT, 'Y'):
                        self.y = float(root.ROW.GEOM.SDO_POINT.Y)
                    if hasattr(root.ROW.GEOM.SDO_POINT, 'Z'):
                        self.z = float(root.ROW.GEOM.SDO_POINT.Z)
            if hasattr(root.ROW, 'ACCESS_CODE'):
                self.access_code = root.ROW.ACCESS_CODE
            if hasattr(root.ROW, 'ENTRYDATE'):
                self.entry_date = root.ROW.ENTRYDATE
            if hasattr(root.ROW, 'COUNTRY'):
                self.country = root.ROW.COUNTRY

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
                        self.x, self.y, self.z
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
                    'siteDescription': self.site_description,
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
        print(json.dumps(site))
        return Response(
            json.dumps(site),
            mimetype='application/vnd.geo+json'
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


if __name__ == '__main__':
    s = Site(17943)
    s._populate_from_oracle_api()
    print(s.export_nemsr_geojson())
