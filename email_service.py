import boto3
from botocore.exceptions import ClientError

# Send an email with Amazon SES
# You can find more information here:
# https://docs.aws.amazon.com/ses/latest/DeveloperGuide/send-email-api.html
# https://docs.aws.amazon.com/ses/latest/DeveloperGuide/examples-send-using-smtp.html

def body_text(name,phase,epsilon,prop,cid,atoms,geom,charge,user_name,energy,dipole,Tdip):

         if user_name is not None:  
            message = "Dear "+user_name+",\n" 
         else: 
            message = "Dear User,\n" 
         if prop in ["dipole moment","excitation energy"]: 
            message += "The calculation you requested on the {} of {} in {} is completed.\n".format(prop,name,phase)
         else : 
            message += "The calculation you requested on the {} of {} is completed.\n".format(prop,name,phase)
         message += "These are the results:\n"
         message += "\n"
         message += "PubChem CID: "+str(cid)+"\n"
         message += "PubChem link: https://pubchem.ncbi.nlm.nih.gov/compound/"+name+"\n"
         message += "\n"
         message += "Molecular geometry used for the calculation:\n"
         for i in range(len(atoms)):
              message += "{}   {:.6f}  {:.6f}  {:.6f}\n".format(atoms[i],geom[i][0],geom[i][1],geom[i][2])
         message += "\n"
         message += "Level of theory: PBE0/3-21G\n"
         if prop in ["dipole moment","excitation energy"]: 
            message += "Dielectric constant used: "+str(epsilon)+"\n"
         message += "Wave function convergence threshold: 3e-3 a.u.\n"
         message += "\n"
         message += "Results:\n"
         if prop == "dipole moment":
            message += "SCF Energy: {:.6f} (a.u.)\n".format(energy)
            message += "Dipole moment: {:.1f} Debye\n".format(dipole)
         elif prop == "excitation energy":
            message += "S0 Energy: {:.6f} (a.u.)\n".format(energy[0])
            message += "S1 Energy: {:.6f} (a.u.), Excitation Energy: {:.1f} (eV), |Transition Dipole Moment|: {:.3f} (a.u.)\n".format(energy[1],((energy[1]-energy[0])*27.2114),Tdip[0])
            message += "S2 Energy: {:.6f} (a.u.), Excitation Energy: {:.1f} (eV), |Transition Dipole Moment|: {:.3f} (a.u.)\n".format(energy[2],((energy[2]-energy[0])*27.2114),Tdip[1])
         elif prop == "solvatochromic shift":
            message += "Gas:\n"
            message += "S0 Energy: {:.6f} (a.u.)\n".format(energy[0][0])
            message += "S1 Energy: {:.6f} (a.u.), Excitation Energy: {:.1f} (eV), |Transition Dipole Moment|: {:.3f} (a.u.)\n".format(energy[0][1],((energy[0][1]-energy[0][0])*27.2114),Tdip[0][0])
            message += "S2 Energy: {:.6f} (a.u.), Excitation Energy: {:.1f} (eV), |Transition Dipole Moment|: {:.3f} (a.u.)\n".format(energy[0][2],((energy[0][2]-energy[0][0])*27.2114),Tdip[0][1])
            message += "\n"
            message += "Water:\n"
            message += "S0 Energy: {:.6f} (a.u.)\n".format(energy[1][0])
            message += "S1 Energy: {:.6f} (a.u.), Excitation Energy: {:.1f} (eV), |Transition Dipole Moment|: {:.3f} (a.u.)\n".format(energy[1][1],((energy[1][1]-energy[1][0])*27.2114),Tdip[1][0])
            message += "S2 Energy: {:.6f} (a.u.), Excitation Energy: {:.1f} (eV), |Transition Dipole Moment|: {:.3f} (a.u.)\n".format(energy[1][2],((energy[1][2]-energy[1][0])*27.2114),Tdip[1][1])
         message += "\n"
         message += "The calculation has been performed using TeraChem v1.9 and the TeraChem Cloud infrastructure. Please cite these papers: https://mtzweb.stanford.edu/software.\n"
         message += "\n"
         message += "Thank you for using ChemVox!\n" 
         message += "\n"
         message += "For any inquiries, contact the ChemVox team at chemvox.mtz@gmail.com.\n" 

         return message



def send_email(RECIPIENT,BODY_TEXT):

# Insert your data 
         SENDER = "insert sender email"
         AWS_REGION = "insert AWS region"
# 
         SUBJECT = "ChemVox Calculation Results"

         # The character encoding for the email.
         CHARSET = "UTF-8"
         
         # Create a new SES resource and specify a region.

# Insert your data 
         client = boto3.client('ses',region_name=AWS_REGION,aws_access_key_id=TOADD,aws_secret_access_key=TOADD)
         
         # Provide the contents of the email.
         response = client.send_email(
             Destination={
                 'ToAddresses': [
                     RECIPIENT,
                 ],
             },
             Message={
                 'Body': {
                     'Text': {
                         'Charset': CHARSET,
                         'Data': BODY_TEXT,
                     },
                 },
                 'Subject': {
                     'Charset': CHARSET,
                     'Data': SUBJECT,
                 },
             },
             Source=SENDER,
         )



