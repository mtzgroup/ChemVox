# -*- coding: utf-8 -*-

# ChemVox 

import logging

from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model.ui import SimpleCard
from ask_sdk_model.ui import StandardCard
from ask_sdk_model import Response

from ask_sdk_model.services.directive import (SendDirectiveRequest, Header, SpeakDirective)

from ask_sdk_model.ui import AskForPermissionsConsentCard
from ask_sdk_model.services import ServiceException

from ask_sdk_model.ui import Image

from ask_sdk_model.services.ups import UpsServiceClient


from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_model.services import ServiceClientFactory
from ask_sdk_core.api_client import DefaultApiClient

from multiprocessing.pool import ThreadPool
import numpy as np
import smtplib, ssl
import time
import requests 
import json
import random 

from pubchem import get_cids
from calculations import launch_calculation,get_parameters,get_capabilities,solvatochromic


sb = CustomSkillBuilder(api_client=DefaultApiClient())

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

permissions = ["alexa::profile:email:read","alexa::profile:given_name:read"]

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        global user_name
        global receiver_email 

        req_envelope = handler_input.request_envelope
        if not (req_envelope.context.system.user.permissions and req_envelope.context.system.user.permissions.consent_token):
              user_name = '' 
              receiver_email = None 
        else:
              apiaccessToken = handler_input.request_envelope.context.system.api_access_token
              key = 'Bearer ' + apiaccessToken
              headers = {"Host":"api.amazonalexa.com","Authorization": key, "Accept": "application/json"}
              URL = "https://api.amazonalexa.com/v2/accounts/~current/settings/Profile.givenName"
              jname = requests.get(url = URL, headers=headers)
              user_name = jname.json()
              if not isinstance(user_name, str): user_name = '' 

              URL = "https://api.amazonalexa.com/v2/accounts/~current/settings/Profile.email"
              jemail = requests.get(url = URL, headers=headers)
              receiver_email = jemail.json()  
              if not isinstance(receiver_email, str):  receiver_email = None

        if receiver_email is None or user_name == '':
           speech_text = "Welcome "+user_name+", I am ChemVox, the voice of TeraChem. If you grant the permissions to access your email address and name in the skill setting, I will email you the results. How can I help you?"
           handler_input.response_builder.speak(speech_text).set_card(
            AskForPermissionsConsentCard(permissions=permissions)).set_should_end_session(
            False)
        else:
           speech_text = "Welcome "+user_name+", I am ChemVox, the voice of TeraChem. How can I help you?"
           small="https://chemvox.s3.us-east-2.amazonaws.com/"+str(random.randint(1,6))+".png"
           pict = Image(small)
           handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,pict)).set_should_end_session(
            False)

        return handler_input.response_builder.response


class DipoleIntentHandler(AbstractRequestHandler):
    """Handler for Compute Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("dipole")(handler_input)

    def progressive_response(self,handler_input,sentence):
        request_id_holder = handler_input.request_envelope.request.request_id
        directive_header = Header(request_id=request_id_holder)
        speech = SpeakDirective(speech=sentence)

        directive_request = SendDirectiveRequest(header=directive_header, directive=speech)
        directive_service_client = handler_input.service_client_factory.get_directive_service()
        directive_service_client.enqueue(directive_request)
#        time.sleep(1)
        return

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        skill_locale = handler_input.request_envelope.request.locale

        name = slots["name"].value
        phase = slots["phase"].value
        
        if phase is None: phase='gas'
	    
        phases = get_capabilities()
        s1 = False
               
        if phase in phases:
           sentence = "Let me search for "+name+" on my database"
           self.progressive_response(handler_input,sentence)

# check molecule on Pubchem
           cids = get_cids(name, 'name')
           if not cids:
               speech_text  = "Sorry, I could not find {} on PubChem. What else can I do for you?".format(name)
           else:
               Natoms,atoms,geom,charge = get_parameters(cids)

               if geom is None:
                    speech_text  = "Sorry, I could not find the coordinates of {} on PubChem. What else can I do for you?".format(name)

               else:
# run calculation on TCC 
                    sentence = "I Launched the calculation on TeraChem Cloud."
                    self.progressive_response(handler_input,sentence)
         
                    pool = ThreadPool(processes=1)
                    async_result = pool.apply_async(launch_calculation,(s1, name,cids,phase,phases[phase], atoms, geom, charge,receiver_email,user_name,True))
                         
                    speech_text = None
                    try :
                        speech_text = async_result.get(timeout=5)
                    except :
                        if receiver_email is None:
                           speech_text = "The calculation is taking too long. If you grant the permission, I will email you the results. What else can I do for you?" 
                        else:
                           speech_text = "The calculation is taking too long. I will email you the results. What else can I do for you?" 

        elif phase == 'solvent':
           speech_text = "Please, try again, specifying the solvent. You can ask for calculations in solvent like chloroform, water and many others."
        elif phase not in phases:
           speech_text = "Please, try again, I do not know that phase. You can ask for calculations in gas or in solvent like chloroform, water and many others."

# type: (HandlerInput) -> Response
        small="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"+name.replace(" ", "")+"/PNG"
        structure = Image(small)
        handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,structure)).set_should_end_session(
            False)
        return handler_input.response_builder.response

class AbsorptionIntentHandler(AbstractRequestHandler):
    """Handler for Compute Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("absorption")(handler_input)

    def progressive_response(self,handler_input,sentence):
        request_id_holder = handler_input.request_envelope.request.request_id
        directive_header = Header(request_id=request_id_holder)
        speech = SpeakDirective(speech=sentence)

        directive_request = SendDirectiveRequest(header=directive_header, directive=speech)
        directive_service_client = handler_input.service_client_factory.get_directive_service()
        directive_service_client.enqueue(directive_request)
#        time.sleep(1)
        return

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        skill_locale = handler_input.request_envelope.request.locale

        name = slots["name"].value
        phase = slots["phase"].value

        phases = get_capabilities()
        if phase is None: phase='gas'
        s1 = True  
       
        if phase in phases:
           sentence = "Let me search for "+name+" on my database"
           self.progressive_response(handler_input,sentence)

# check molecule on Pubchem
           cids = get_cids(name, 'name')
           if not cids:
               speech_text  = "Sorry, I could not find {} on PubChem. What else can I do for you?".format(name)
           else:
               Natoms,atoms,geom,charge = get_parameters(cids)

               if geom is None:
                    speech_text  = "Sorry, I could not find the coordinates of {} on PubChem. What else can I do for you?".format(name)

               else:
# run calculation on TCC 
                    sentence = "I Launched the calculation on TeraChem Cloud."
                    self.progressive_response(handler_input,sentence)
         
                    pool = ThreadPool(processes=1)
                    async_result = pool.apply_async(launch_calculation,(s1, name,cids, phase,phases[phase], atoms, geom, charge,receiver_email,user_name,True))

                    speech_text = None
                    try :
                        speech_text = async_result.get(timeout=5)
                    except :
                        if receiver_email is None:
                           speech_text = "The calculation is taking too long. If you grant the permission, I will email you the results. What else can I do for you?" 
                        else:
                           speech_text = "The calculation is taking too long. I will email you the results. What else can I do for you?" 

        elif phase == 'solvent':
           speech_text = "Please, try again, specifying the solvent. You can ask for calculations in solvent like chloroform, water and many others."
        elif phase not in phases:
           speech_text = "Please, try again, I do not know that phase. You can ask for calculations in gas or in solvent like chloroform, water and many others."

# type: (HandlerInput) -> Response
        small="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"+name.replace(" ", "")+"/PNG"
        structure = Image(small)
        handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,structure)).set_should_end_session(
            False)
        return handler_input.response_builder.response

class ShiftIntentHandler(AbstractRequestHandler):
    """Handler for Compute Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("shift")(handler_input)

    def progressive_response(self,handler_input,sentence):
        request_id_holder = handler_input.request_envelope.request.request_id
        directive_header = Header(request_id=request_id_holder)
        speech = SpeakDirective(speech=sentence)

        directive_request = SendDirectiveRequest(header=directive_header, directive=speech)
        directive_service_client = handler_input.service_client_factory.get_directive_service()
        directive_service_client.enqueue(directive_request)
#        time.sleep(1)
        return

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        skill_locale = handler_input.request_envelope.request.locale

        name = slots["name"].value

        s1 = True  
       
        sentence = "Let me search for "+name+" on my database"
        self.progressive_response(handler_input,sentence)

# check molecule on Pubchem
        cids = get_cids(name, 'name')
        if not cids:
           speech_text  = "Sorry, I could not find {} on PubChem. What else can I do for you?".format(name)
        else:
           Natoms,atoms,geom,charge = get_parameters(cids)

           if geom is None:
              speech_text  = "Sorry, I could not find the coordinates of {} on PubChem. What else can I do for you?".format(name)

           else:
# run calculation on TCC 
              sentence = "I Launched the calculation on TeraChem Cloud."
              self.progressive_response(handler_input,sentence)
         
              pool = ThreadPool(processes=1)
              async_result = pool.apply_async(solvatochromic,(s1, name,cids, atoms, geom, charge,receiver_email,user_name))

              speech_text = None
              try :
                  speech_text = async_result.get(timeout=5)
              except :
                  if receiver_email is None:
                     speech_text = "The calculation is taking too long. If you grant the permission, I will email you the results. What else can I do for you?" 
                  else:
                     speech_text = "The calculation is taking too long. I will email you the results. What else can I do for you?" 

# type: (HandlerInput) -> Response
        small="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"+name.replace(" ", "")+"/PNG"
        structure = Image(small)
        handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,structure)).set_should_end_session(
            False)
        return handler_input.response_builder.response

class SolventIntentHandler(AbstractRequestHandler):
    """Handler for Compute Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("solvent")(handler_input)

    def handle(self, handler_input):

        speech_text = "You can ask for calculations in gas, water, acetonitrile, methanol, chloroform, dichloromethane, toluene, cyclohexane, acetone, tetrahydrofuran, dimethylsulfoxide. What would you like me to compute?"

        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard("ChemVox", speech_text)).set_should_end_session(
            False)
        return handler_input.response_builder.response

class MethodIntentHandler(AbstractRequestHandler):
    """Handler for Compute Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("method")(handler_input)

    def handle(self, handler_input):

        speech_text = "I am using PBE0 3 2 1 G and the COSMO model for the calculations in solvent phase. What would you like me to compute?"

        handler_input.response_builder.speak(speech_text).set_card(
            SimpleCard("ChemVox", speech_text)).set_should_end_session(
            False)
        return handler_input.response_builder.response

class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "I can compute the dipole moment, the excitation energy of the brightest excited state, and the solvatochromic shift between water and gas phase. What would you like me to compute?"

        handler_input.response_builder.speak(speech_text).ask(
            speech_text).set_card(SimpleCard(
                "ChemVox", speech_text))
        return handler_input.response_builder.response


class MoleculeIntentHandler(AbstractRequestHandler):
    """Handler for Compute Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("molecule")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots
        skill_locale = handler_input.request_envelope.request.locale

        name = slots["name"].value
       
# check molecule on Pubchem
        cids = get_cids(name, 'name')
        if not cids:
           speech_text  = "Sorry, I could not find {} on PubChem. What else can I do for you?".format(name)
        else:
           Natoms,atoms,geom,charge = get_parameters(cids)

           if geom is None:
              speech_text  = "Sorry, I could not find the coordinates of {} on PubChem. What else can I do for you?".format(name)
           else:
              speech_text  = "Yes, this is the structure of {} and you can ask for calculations on it. What else can I do for you?".format(name)

# type: (HandlerInput) -> Response
        small="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"+name.replace(" ", "")+"/PNG"
        structure = Image(small)
        handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,structure)).set_should_end_session(
            False)
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "Thank you for using TeraChem! " \
                    "Have a nice day!"
        small="https://chemvox.s3.us-east-2.amazonaws.com/"+str(random.randint(1,6))+".png"
        pict = Image(small)
        handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,pict)).set_should_end_session(
            True)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """
    This handler will not be triggered except in supported locales,
    so it is safe to deploy on any locale.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "Sorry I didn't get that. Can you repeat?"
        reprompt = "Sorry I didn't get that. Can you repeat?"
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("SessionEndedRequest")(handler_input) or
                is_intent_name("AMAZON.NoIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "Thank you for using TeraChem! " \
                    "Have a nice day! "

        small="https://chemvox.s3.us-east-2.amazonaws.com/"+str(random.randint(1,6))+".png"
        pict = Image(small)
        handler_input.response_builder.speak(speech_text).set_card(
            StandardCard("ChemVox", speech_text,pict)).set_should_end_session(
            True)
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Catch all exception handler, log exception and
    respond with custom message.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speech = "Please try again!!"
        handler_input.response_builder.speak(speech).ask(speech)

        return handler_input.response_builder.response


sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(DipoleIntentHandler())
sb.add_request_handler(AbsorptionIntentHandler())
sb.add_request_handler(ShiftIntentHandler())
sb.add_request_handler(SolventIntentHandler())
sb.add_request_handler(MethodIntentHandler())
sb.add_request_handler(MoleculeIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

handler = sb.lambda_handler()



