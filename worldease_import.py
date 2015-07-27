from jsonrpclib import Server as ServerProxy
import logging
import json
import pdb
from lxml import etree
from lxml.builder import ElementMaker
import time
import os
import getpass
import pprint


HOST = 'https://your host here'
PORT = '8000'
DB = 'yourdb'

NAME_SPACE = "x-schema:OpenShipments.xdr"
XML_NS = "{%s}" % NAME_SPACE

XML_IMPORT_DIR = 'blah'

pp = pprint.PrettyPrinter(indent=4)

class Tryton(object):

    def __init__(self, url, credentials):
        self.server = ServerProxy(url, verbose=0)
        self.user, self.cookie = self.server.common.server.login(
            credentials['USER'],
            credentials['PASSWORD'])
        self.pref = self.server.model.res.user.get_preferences(
            self.user,
            self.cookie, True, {})

    def execute(self, method, *args):
        args += (self.pref,)
        try:
            return getattr(self.server, method)(self.user, self.cookie, *args)
        except TypeError:
            print(jsonrpclib.history.request)
            a = json.loads(jsonrpclib.history.response)
            raise TypeError('%s: %s' % (a['error'][0], a['error'][1][0]))


if __name__ == "__main__":

    creds = {}
    creds['USER'] = raw_input('Please enter Tryton username :')
    creds['PASSWORD'] = getpass.getpass('Please enter Tryton password :')

    E = ElementMaker(namespace=NAME_SPACE)
    a = Tryton("%s:%s/%s" % (HOST, PORT, DB), creds )
    while True :
        # Look for new WOrldship shipments
        worldease_shipments = a.execute('model.stock.shipment.out.search' \
        ,[('state','=','packed'), ('tracking_number','=',None), ('ups_service_type.name','=','UPS Standard')])
        for shipment in worldease_shipments :
            # Get it!
            worldship_xml =  a.execute('model.stock.shipment.out.get_worldship_xml', [shipment])
            # etree won't parse with encoding
            doc = etree.fromstring(worldship_xml[0]['worldship_xml'].replace('encoding="UTF-8"',''))
            f = open('C:/UPS/WSTD/ImpExp/XML Auto Import/%s.xml' % shipment, 'w' )
            # Do it!
            doc.find(".//{0}ServiceType".format(XML_NS)).text = 'Standard'
            doc.find(".//{0}OpenShipment".format(XML_NS)).attrib['ShipmentOption'] = 'SC'
            doc.find(".//{0}DescriptionOfGoods".format(XML_NS)).text = 'Woodworking Tools and Accessories'
            # TODO take this out once OL merges some stuff      =========================================
            doc.find(".//{0}ShipTo/{0}StateProvinceCounty".format(XML_NS)).text \
                 = doc.find(".//{0}ShipTo/{0}StateProvinceCounty".format(XML_NS)).text.partition('-')[2]
            doc.find(".//{0}ShipFrom/{0}StateProvinceCounty".format(XML_NS)).text \
                 = doc.find(".//{0}ShipFrom/{0}StateProvinceCounty".format(XML_NS)).text.partition('-')[2]
            doc.find(".//{0}ShipTo/{0}CompanyOrName".format(XML_NS)).text = \
                doc.find(".//{0}ShipTo/{0}Attention".format(XML_NS)).text
            #===========================================================================================
            open_shipment =  doc.find(".//"+XML_NS+"OpenShipment")
            for item in  a.execute('model.stock.shipment.out.read', [shipment],['outgoing_moves'])[0]['outgoing_moves']:
                item_details = a.execute('model.stock.move.read',[item])
                if str(item_details[0]['quantity']) != '0.0':
                    good =  E.Goods(
                        E.PartNumber(item_details[0]['rec_name'].partition('[')[2].partition(']')[0]),
                        E.DescriptionOfGood(item_details[0]['rec_name'].partition(']')[2].strip()),
                        E('Inv-NAFTA-CO-CountryTerritoryOfOrigin','US'),
                        E.InvoiceUnits(str(item_details[0]['quantity'])),
                        E.InvoiceUnitOfMeasure('Each'),
                        # Worldease does not like a value of $0 for customs so we substitute a penny if so.
                        E('Invoice-SED-UnitPrice',str(float(item_details[0]['unit_price']['decimal']) or 0.01))
                 )
                    open_shipment.append(good)
                    print (etree.tostring(good, pretty_print=True))
            proceed = raw_input('Items correct (y/n))? ')
            if proceed == 'y' :
                f.write(etree.tostring(doc, pretty_print=True))
                f.close()
            # Look for file modified by worldship
            # Give Worldship a little time
                time.sleep(10)
                doc2 = etree.parse('C:/UPS/WSTD/ImpExp/XML Auto Import/%s.Out' % shipment)
                tracking_number = doc2.find(".//{0}TrackingNumber".format(XML_NS)).text
                shipping_cost = doc2.find(".//{0}ShipmentCharges/{0}Rate/{0}Negotiated".format(XML_NS)).text
                # Python Decimal not json serializable. THis encoder borrowed from trytond.protocols.jsonrpc.JSONEncoder
                # Don't feel like installing extra crap
                shipping_cost_Decimal_encode = {'__class__':'Decimal', 'decimal':shipping_cost}
                # No currency code for Worldship XML returned. Always US Dollars
                currency = 172
                res = a.execute('model.stock.shipment.out.write',[shipment], {'tracking_number': unicode(tracking_number),'cost': shipping_cost_Decimal_encode,'cost_currency': currency,})

        # Go to sleep my friend, let's wake up every
        time.sleep(5)
