import os
from qgis.core import *
from qgis.analysis import QgsNativeAlgorithms
from qgis.PyQt.QtCore import QVariant
import processing
from processing.core.Processing import Processing

   
    
class Gates_green_areas(QgsProcessingAlgorithm):
    def __init__(self):
        super().__init__()
        self.modes = ['A', 'ABC']  

    def initAlgorithm(self, config=None):
        
        self.addParameter(QgsProcessingParameterString('mode', 'Modalità di esecuzione', defaultValue='ABC'))
        self.addParameter(QgsProcessingParameterVectorLayer('green_areas', 'green_areas', types=[QgsProcessing.TypeVectorAnyGeometry], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('gate_osm', 'Gate_OSM', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('streets', 'streets', types=[QgsProcessing.TypeVectorAnyGeometry], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Gates', 'GATES', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):

        mode = parameters['mode']
        
        feedback = QgsProcessingMultiStepFeedback(16, model_feedback)
        results = {}
        outputs = {}
        if mode == 'ABC':
            # Da poligoni a linee
            alg_params = {
                'INPUT': parameters['green_areas'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['DaPoligoniALinee'] = processing.run('native:polygonstolines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}
    
            # Estrai per posizione
            alg_params = {
                'INPUT': parameters['streets'],
                'INTERSECT': parameters['green_areas'],
                'PREDICATE': [0,1,7],  # interseca,contiene,attraversa
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['EstraiPerPosizione'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(2)
            if feedback.isCanceled():
                return {}
    
            # Estrai entro una distanza
            alg_params = {
                'DISTANCE': 10,
                'INPUT': parameters['gate_osm'],
                'REFERENCE': parameters['green_areas'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['EstraiEntroUnaDistanza'] = processing.run('native:extractwithindistance', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(3)
            if feedback.isCanceled():
                return {}
    
            # GATE_B
            alg_params = {
                'INPUT': outputs['EstraiPerPosizione']['OUTPUT'],
                'INPUT_FIELDS': [''],
                'INTERSECT': outputs['DaPoligoniALinee']['OUTPUT'],
                'INTERSECT_FIELDS': [''],
                'INTERSECT_FIELDS_PREFIX': None,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Gate_b'] = processing.run('native:lineintersections', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(4)
            if feedback.isCanceled():
                return {}
    
            # GATE_A
            alg_params = {
                'DISCARD_NONMATCHING': False,
                'FIELDS_TO_COPY': [''],
                'INPUT': outputs['EstraiEntroUnaDistanza']['OUTPUT'],
                'INPUT_2': parameters['green_areas'],
                'MAX_DISTANCE': None,
                'NEIGHBORS': 1,
                'PREFIX': None,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Gate_a'] = processing.run('native:joinbynearest', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(5)
            if feedback.isCanceled():
                return {}
    
            # Calcolatore Campi - GATE B
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'GATE_B',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2,  # Testo (stringa)
                'FORMULA': 'if ("osm_type"= \'way\',\'B\',NULL) ',
                'INPUT': outputs['Gate_b']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['CalcolatoreCampiGateB'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(6)
            if feedback.isCanceled():
                return {}
    
            # Calcolatore Campi - GATE A
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'GATE_A',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2,  # Testo (stringa)
                'FORMULA': 'if ("barrier"= \'gate\',\'A\',NULL)',
                'INPUT': outputs['Gate_a']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['CalcolatoreCampiGateA'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(7)
            if feedback.isCanceled():
                return {}
    
            # Fondi vettori
            alg_params = {
                'CRS': None,
                'LAYERS': [outputs['CalcolatoreCampiGateA']['OUTPUT'],outputs['CalcolatoreCampiGateB']['OUTPUT']],
                'OUTPUT':  'memory:'
            }
            outputs['FondiVettori'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['FondiVettori'] = outputs['FondiVettori']['OUTPUT']
    
            feedback.setCurrentStep(8)
            if feedback.isCanceled():
                return {}
    
            # Estrai Aree Verdi che abbiano almeno un gate A/B vicino
            alg_params = {
                'DISTANCE': 10,
                'INPUT': parameters['green_areas'],
                'REFERENCE': outputs['FondiVettori']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['EstraiAreeVerdiCheAbbianoAlmenoUnGateAbVicino'] = processing.run('native:extractwithindistance', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(9)
            if feedback.isCanceled():
                return {}
    
            # Join attributes by field value
            alg_params = {
                'DISCARD_NONMATCHING': False,
                'FIELD': 'fid',
                'FIELDS_TO_COPY': ['fid'],
                'FIELD_2': 'fid',
                'INPUT': parameters['green_areas'],
                'INPUT_2': outputs['EstraiAreeVerdiCheAbbianoAlmenoUnGateAbVicino']['OUTPUT'],
                'METHOD': 1,  # Prendi solamente gli attributi del primo elemento corrispondente (uno-a-uno)
                'PREFIX': 'join_',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['JoinAttributesByFieldValue'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(10)
            if feedback.isCanceled():
                return {}
    
            # Extract by expression
            alg_params = {
                'EXPRESSION': 'join_fid is null',
                'INPUT': outputs['JoinAttributesByFieldValue']['OUTPUT'],
                'OUTPUT':  'memory:'
            }
            outputs['ExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['ExtractByExpression'] = outputs['ExtractByExpression']['OUTPUT']
    
            feedback.setCurrentStep(11)
            if feedback.isCanceled():
                return {}
    
            # GATE_C
            alg_params = {
                'DISTANCE': 100,
                'END_OFFSET': 0,
                'INPUT': outputs['ExtractByExpression']['OUTPUT'],
                'START_OFFSET': 0,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Gate_c'] = processing.run('native:pointsalonglines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(12)
            if feedback.isCanceled():
                return {}
    
            # Calcolatore Campi - GATE C
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'GATE_C',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2,  # Testo (stringa)
                'FORMULA': "'C'",
                'INPUT': outputs['Gate_c']['OUTPUT'],
                'OUTPUT':  'memory:'
            }
            outputs['CalcolatoreCampiGateC'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['CalcolatoreCampiGateC'] = outputs['CalcolatoreCampiGateC']['OUTPUT']
    
            feedback.setCurrentStep(13)
            if feedback.isCanceled():
                return {}
    
            # Fondi vettori finale
            alg_params = {
                'CRS': None,
                'LAYERS': [outputs['CalcolatoreCampiGateA']['OUTPUT'],outputs['CalcolatoreCampiGateB']['OUTPUT'],outputs['CalcolatoreCampiGateC']['OUTPUT']],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FondiVettoriFinale'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            feedback.setCurrentStep(14)
            if feedback.isCanceled():
                return {}
    
            # Calcolatore Campi - tipo
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'TIPO_GATE',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2,  # Testo (stringa)
                'FORMULA': 'if ("GATE_A" is not null,\'A\',if ("GATE_B" is not null,\'B\', \'C\'))',
                'INPUT': outputs['FondiVettoriFinale']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['CalcolatoreCampiTipo'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['Gate'] = outputs['CalcolatoreCampiTipo']['OUTPUT']
    
            feedback.setCurrentStep(15)
            if feedback.isCanceled():
                return {}
    
            # Retain fields
            alg_params = {
                'FIELDS': ['TIPO_GATE'],
                'INPUT': outputs['CalcolatoreCampiTipo']['OUTPUT'],
                'OUTPUT': parameters['Gates']
            }
            outputs['RetainFields'] = processing.run('native:retainfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results['Gates'] = outputs['RetainFields']['OUTPUT']
            return results
        else:

            
            feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
            results = {}
            outputs = {}
            
            # Estrai entro una distanza (10 m da aree verdi)
            alg_params = {
                'DISTANCE': 10,
                'INPUT': parameters['gate_osm'],
                'REFERENCE': parameters['green_areas'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['GateVicini'] = processing.run(
                'native:extractwithindistance', 
                alg_params, 
                context=context, 
                feedback=feedback, 
                is_child_algorithm=True
            )
            
            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}
            
            # Join con aree verdi (per confermare la vicinanza)
            alg_params = {
                'DISCARD_NONMATCHING': False,
                'FIELDS_TO_COPY': [''],
                'INPUT': outputs['GateVicini']['OUTPUT'],
                'INPUT_2': parameters['green_areas'],
                'MAX_DISTANCE': None,
                'NEIGHBORS': 1,
                'PREFIX': None,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['GateJoin'] = processing.run(
                'native:joinbynearest', 
                alg_params, 
                context=context, 
                feedback=feedback, 
                is_child_algorithm=True
            )
            
            feedback.setCurrentStep(2)
            if feedback.isCanceled():
                return {}
            
            # Aggiungi campo GATE_A
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'GATE_A',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2,  # stringa
                'FORMULA': 'if ("barrier" = \'gate\' OR "entrance" = \'yes\' OR "barrier" = \'entrance\', \'A\', NULL)',
                'INPUT': outputs['GateJoin']['OUTPUT'],
                'OUTPUT': parameters['Gates']
            }
            outputs['CalcolatoreCampiGateA'] = processing.run(
                'native:fieldcalculator', 
                alg_params, 
                context=context, 
                feedback=feedback, 
                is_child_algorithm=True
            )
            results['Gates'] = outputs['CalcolatoreCampiGateA']['OUTPUT']
            
            return results        

    def name(self):
        return 'gates_green_areas'

    def displayName(self):
        return 'gates_green_areas'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Gates_green_areas()
        
        
