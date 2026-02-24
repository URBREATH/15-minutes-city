import os
from qgis.core import *
from qgis.analysis import QgsNativeAlgorithms
from qgis.PyQt.QtCore import QVariant
import processing
from processing.core.Processing import Processing

   
class GatesA(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('green_areas', 'green_areas', types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterVectorLayer('gate_osm', 'Gate_OSM', types=[QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterField('id_green_area', 'Campo ID univoco', type=QgsProcessingParameterField.Any))
        self.addParameter(QgsProcessingParameterNumber('park_gates_osm_buffer_m', 'Buffer gate_osm', type=QgsProcessingParameterNumber.Double, defaultValue=10))
        self.addParameter(QgsProcessingParameterFeatureSink('Gates', 'Gates', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True))

    def processAlgorithm(self, parameters, context, feedback):
        feedback = QgsProcessingMultiStepFeedback(4, feedback)
        results = {}
        outputs = {}

        id_green_area = parameters['id_green_area']
        buffer_m = parameters['park_gates_osm_buffer_m']
        temp_dir = os.path.join(QgsProject.instance().homePath(), "temp_gates")
        temp_gateVicini = os.path.join(temp_dir, "gateVicini.gpkg")
        temp_gateJoin = os.path.join(temp_dir, "gateJoin.gpkg")
        temp_gateA = os.path.join(temp_dir, "gateA.gpkg")
        # Estrai punti gate vicino ai parchi
        alg_params = {
            'DISTANCE': buffer_m,
            'INPUT': parameters['gate_osm'],
            'REFERENCE': parameters['green_areas'],
            'OUTPUT': temp_gateVicini
        }
        outputs['GateVicini'] = processing.run('native:extractwithindistance', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled(): return {}

        # Join con parchi
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELDS_TO_COPY': [''],
            'INPUT': outputs['GateVicini']['OUTPUT'],
            'INPUT_2': parameters['green_areas'],
            'MAX_DISTANCE': None,
            'NEIGHBORS': 1,
            'PREFIX': None,
            'OUTPUT': temp_gateJoin
        }
        outputs['GateJoin'] = processing.run('native:joinbynearest', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        feedback.setCurrentStep(2)
        if feedback.isCanceled(): return {}

        # Aggiungi campo GATE_A
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'GATE_A',
            'FIELD_TYPE': 2,
            'FIELD_PRECISION': 0,
            'FORMULA': "if (\"barrier\" = 'gate' OR \"entrance\" = 'yes' OR \"barrier\" = 'entrance', 'A', NULL)",
            'INPUT': outputs['GateJoin']['OUTPUT'],
            'OUTPUT': temp_gateA
        }
        outputs['CalcolatoreGateA'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        feedback.setCurrentStep(3)
        if feedback.isCanceled(): return {}

        # Salva layer finale con campi principali
        final_params = {
            'INPUT': outputs['CalcolatoreGateA']['OUTPUT'],
            'FIELDS': ['unique_id', 'GATE_A'],
            'OUTPUT': parameters['Gates']
        }
        processing.run('native:retainfields', final_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Gates'] = parameters['Gates']
        return results

    def name(self): return 'gates_a'
    def displayName(self): return 'Gates A'
    def group(self): return ''
    def groupId(self): return ''
    def createInstance(self): return GatesA()
    
    
class GatesB(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('green_areas', 'green_areas', types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterVectorLayer('streets', 'streets', types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField('id_green_area', 'Campo ID univoco', type=QgsProcessingParameterField.Any))
        self.addParameter(QgsProcessingParameterFeatureSink('Gates', 'Gates', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True))

    def processAlgorithm(self, parameters, context, feedback):
        feedback = QgsProcessingMultiStepFeedback(3, feedback)
        results = {}
        outputs = {}

        id_green_area = parameters['id_green_area']

        temp_dir = os.path.join(QgsProject.instance().homePath(), "temp_gates")
        temp_streetsNga = os.path.join(temp_dir, "streetsNga.gpkg")
        temp_polygon = os.path.join(temp_dir, "polygon.gpkg")
        temp_gateB = os.path.join(temp_dir, "gateB.gpkg")
        
        # Streets ∩ Green Areas
        alg_params = {
            'INPUT': parameters['streets'],
            'INTERSECT': parameters['green_areas'],
            'PREDICATE': [0,1,7],
            'OUTPUT': temp_streetsNga
        }
        outputs['EstraiPosizione'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        feedback.setCurrentStep(1)
        if feedback.isCanceled(): return {}

        # Linee dai bordi dei poligoni green
        alg_params = {
            'INPUT': parameters['green_areas'],
            'OUTPUT': temp_polygon
        }
        outputs['DaPoligoniALinee'] = processing.run('native:polygonstolines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        feedback.setCurrentStep(2)
        if feedback.isCanceled(): return {}

        # Intersezione linee streets → Gate B
        alg_params = {
            'INPUT': outputs['EstraiPosizione']['OUTPUT'],
            'INTERSECT': outputs['DaPoligoniALinee']['OUTPUT'],
            'OUTPUT': temp_gateB
        }
        outputs['Gate_b'] = processing.run('native:lineintersections', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        feedback.setCurrentStep(3)
        if feedback.isCanceled(): return {}

        # Calcola campo GATE_B
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'GATE_B',
            'FIELD_TYPE': 2,
            'FIELD_PRECISION': 0,
            'FORMULA': "'B'",
            'INPUT': outputs['Gate_b']['OUTPUT'],
            'OUTPUT': parameters['Gates']
        }
        outputs['CalcolatoreGateB'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Gates'] = outputs['CalcolatoreGateB']['OUTPUT']
        return results

    def name(self): return 'gates_b'
    def displayName(self): return 'Gates B'
    def group(self): return ''
    def groupId(self): return ''
    def createInstance(self): return GatesB()
    
class GatesC(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('green_areas', 'green_areas', types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterNumber('park_gates_virtual_distance_m', 'Distanza Gate Virtuale', type=QgsProcessingParameterNumber.Double, defaultValue=100))
        self.addParameter(QgsProcessingParameterFeatureSink('Gates', 'Gates', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True))

    def processAlgorithm(self, parameters, context, feedback):
        feedback = QgsProcessingMultiStepFeedback(2, feedback)
        results = {}
        outputs = {}

        park_gates_virtual_distance_m = parameters['park_gates_virtual_distance_m']
        temp_dir = os.path.join(QgsProject.instance().homePath(), "temp_gates")
        temp_poltolines = os.path.join(temp_dir, "poltolines.gpkg")
        temp_pointalonglines = os.path.join(temp_dir, "pointalonglines.gpkg")
        
        # Da poligoni a linee
        alg_params = {
            'INPUT': parameters['green_areas'],
            'OUTPUT': temp_poltolines
        }
        outputs['DaPoligoniALinee'] = processing.run('native:polygonstolines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        feedback.setCurrentStep(1)
        if feedback.isCanceled(): return {}

        # Punti lungo linee
        alg_params = {
            'DISTANCE': park_gates_virtual_distance_m,
            'START_OFFSET': 0,
            'END_OFFSET': 0,
            'INPUT': outputs['DaPoligoniALinee']['OUTPUT'],
            'OUTPUT': temp_pointalonglines
        }
        outputs['Gate_c'] = processing.run('native:pointsalonglines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # Calcola campo GATE_C
        alg_params = {
            'FIELD_LENGTH': 10,
            'FIELD_NAME': 'GATE_C',
            'FIELD_TYPE': 2,
            'FIELD_PRECISION': 0,
            'FORMULA': "'C'",
            'INPUT': outputs['Gate_c']['OUTPUT'],
            'OUTPUT': parameters['Gates']
        }
        outputs['CalcolatoreGateC'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Gates'] = outputs['CalcolatoreGateC']['OUTPUT']
        return results

    def name(self): return 'gates_c'
    def displayName(self): return 'Gates C'
    def group(self): return ''
    def groupId(self): return ''
    def createInstance(self): return GatesC()