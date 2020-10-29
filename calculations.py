"""
Basic PyTC client example including authentication
"""
import json
import numpy as np
import client
import math
from multiprocessing.pool import ThreadPool
from pubchem import Compound, get_cids, get_properties                                                                      

from email_service import send_email,body_text

def get_capabilities():
    phases = {'gas': None,
         'water': 78.4, 
         'acetonitrile': 35.7,
         'methanol': 32.6,
         'chloroform': 4.7,
         'dichloromethane': 8.9,
         'toluene': 2.4,
         'cyclohexane': 2.0,
         'acetone': 20.5,
         'tetrahydrofuran': 7.4,
         'thf': 7.4,
         'dimethylsulfoxide': 46.8}

    return phases

def get_parameters(cids):
          
    cids = cids[0]
    try :
          c = Compound.from_cid(cids, record_type='3d')
          Natoms = len(c.to_dict(properties=['atoms'])['atoms'])
          charge = get_properties('charge',cids)[0]['Charge']
          coors = []
          atoms = []
          for i in range(Natoms):
              atoms.append(c.to_dict(properties=['atoms'])['atoms'][i]['element'])
              coors.append([c.to_dict(properties=['atoms'])['atoms'][i]['x'],c.to_dict(properties=['atoms'])['atoms'][i]['y'],c.to_dict(properties=['atoms'])['atoms'][i]['z']])
          geom = np.array(coors)
    except :
          Natoms = None
          atoms = None
          geom = None
          charge = None

    return Natoms,atoms,geom,charge


def launch_calculation(s1, name, cid, phase,epsilon, atoms, geom, charge,receiver_email,user_name,output):

    # Authentication
    USER = "chemvox"
    API_KEY = "9XLx/zMEEInBFjt8GlSB/UwvIWHWL7qDVM5WdqRiJIg="
    URL_SERVER = "http://tccloud.ngrok.io"

    ## Initialize client
    TC = client.Client(url=URL_SERVER, user=USER, api_key=API_KEY,  engine="terachem", verbose=False)

    ## Set the job specification
    tcc_options = {
        # TCC options
        'runtype':      'energy',
        'jobname':      'TerX calculation',
        'units':        'angstrom',
    # TeraChem engine options
        'atoms':        atoms,
        'charge':       charge,
        'spinmult':     1,
        'closed_shell': True,
        'restricted':   True,
        'method':       'pbe0',
        'basis':        '3-21g',
        'convthre':     3.0e-3,
		'precision':     'single',
		'dftgrid':     0,
    }
   
    if epsilon :
        tcc_options['pcm'] = 'cosmo'
        tcc_options['epsilon'] = epsilon

    if s1:
        tcc_options['cis'] = 'yes'
        tcc_options['cisnumstates'] = 2 
        tcc_options['cisconvtol'] = 1.0e-2
        
    
    result = TC.compute(geom, tcc_options)



    if not s1:
        final_number = result['dipole_moment']
        output_speech = 'The dipole moment of {} in {} is: '.format(name,phase)
        output_speech += '{:.1f} Debye. '.format(final_number)
        output_speech += 'What else can I do for you?'
        Tdip = None 

    else :
        Tdip = [math.sqrt(result['cis_transition_dipoles'][i][0]**2+result['cis_transition_dipoles'][i][1]**2+result['cis_transition_dipoles'][i][2]**2) for i in range(2)]
        bright = Tdip.index(max(Tdip)) + 1 # convert to 1 indexed notation
        if bright == 1:
             bright_state = "first"
        elif bright == 2:
             bright_state = "second"

        final_number = [((result['energy'][bright]-result['energy'][0])*27.2114),result['energy'],Tdip]

        output_speech = 'The brightest excited state of {} in {} is the {} state. '.format(name,phase,bright_state)
        output_speech += 'Its energy is {:.1f} electronVolt. '.format(final_number[0])
        output_speech += 'What else can I do for you?'

# Send email with Amazon SES 
#    if receiver_email is not None:
#        if not s1: 
#           prop = "dipole moment"
#        else:
#           prop = "excitation energy"
#        subject = 'ChemVox'
#        message = body_text(name,phase,epsilon,prop,cid,atoms,geom,charge,user_name,result['energy'],result['dipole_moment'],Tdip)
#        pool = ThreadPool(processes=1)
#        async_result = pool.apply_async(send_email,(receiver_email,message))

    if output:
       return output_speech
    else :
       return final_number 
                       
def solvatochromic(s1, name,cid, atoms, geom, charge,receiver_email,user_name):

    pool_gas = ThreadPool(processes=1)   
    gas_results = pool_gas.apply_async(launch_calculation,(s1, name,cid, 'gas',None, atoms, geom, charge,None,user_name,False))
    
    pool_water = ThreadPool(processes=2)
    water_results = pool_water.apply_async(launch_calculation,(s1, name,cid, 'water',78.4, atoms, geom, charge,None,user_name,False))

    gas_val = gas_results.get() 
    wat_val = water_results.get()
    solv_shift = abs(wat_val[0]-gas_val[0])

    output_speech = 'The solvatochromic shift of {} is: '.format(name)
    output_speech += '{:.1f} electronVolt.  '.format(solv_shift)
    output_speech += 'What else can I do for you?'

# Send email with Amazon SES 
#    if receiver_email is not None:
#        prop = "solvatochromic shift"
#        subject = 'ChemVox'
#        message = body_text(name,None,None,prop,cid,atoms,geom,charge,user_name,[gas_val[1],wat_val[1]],None,[gas_val[2],wat_val[2]])
#        pool = ThreadPool(processes=3)
#        async_result = pool.apply_async(send_email,(receiver_email,message))


    return output_speech

