"""Class structures for communicating with the API server over HTTP
"""

import os
from collections import OrderedDict
import json
import numpy as np
import time
import requests

from exceptions import TCCError, HTTPCommunicationError, ServerError

class Client(object):
    """Main class for communication with the TeraChem Cloud API server
    """
    def __init__(self, 
        user=None,
        api_key=None,
        url="http://localhost:80",
        engine='TeraChem',
        verbose=False):
        """Initialize a Client object

        Args:
            user (str): TeraChem Cloud user
            api_key (str): TeraChem Cloud API key
            engine (str): Code to be used for ab initio calculation
            host (str): URL for the TeraChem api server (e.g. http://<hostname>:<port>)
            verbose (bool): print extra info about API interactions
        """
        # Try to get authentication from environment
        if user is not None:
            self.user = str(user)
        else:
            self.user = os.environ['TCCLOUD_USER']
            if self.user is None:
                raise ValueError('"user" not specified and environment variable "TCCLOUD_USER" not set')
        
        if api_key is not None:
            self.api_key = str(api_key)
        else:
            self.api_key = os.environ['TCCLOUD_API_KEY']
            if self.api_key is None:
                raise ValueError('"api_key" not specified and environment variable "TCCLOUD_API_KEY" not set')

        # TCC server options
        self.engine = engine.lower()
        self.url = url
        self.submit_endpoint = "/v1/{}/".format(self.engine)
        self.results_endpoint = "/v1/job/"
        self.help_endpoint = "/v1/docs/"
        self.verbose = verbose

        # try to connect to the server
        payload = {
            'api_key': self.api_key,
            'user_id': self.user
        }

        try:
            r = requests.post(self.url + '/login', json=payload)
        except requests.exceptions.RequestException as e:
            raise HTTPCommunicationError('Error while POSTing login', e)

        if r.status_code != requests.codes.ok:
            raise ServerError(r)

        if self.verbose:
            print('LOGIN> http code: {} response: {}'.format(r.status_code, r.text))

    def help(self):
        """Request allowed keywords from API server
        """
        # Package data according to API server specifications
        payload = {
            'engine': self.engine,
            'api_key': self.api_key,
            'user_id': self.user
        }

        # Send HTTP request
        try:
            r = requests.get(self.url + self.help_endpoint, json=payload)
        except requests.exceptions.RequestException as e:
            raise HTTPCommunicationError('Error while POSTing for docs', e)

        if r.status_code != requests.codes.ok:
            raise ServerError(r)

        response = json.loads(r.text)
        print('API parameters for {} backend (with allowed types and values):'.format(self.engine))
        print(response['docs'])

    def submit(self, geom, options):
        """Pack and send the current tc_config dict as a POST request to the Tornado API server
        This function returns a job_id and a message

        Args:
            geom (np.ndarray or list): Cartesian geometry at which to perform the calculation
            options (dict): Job options to pass to TeraChem Cloud server

        Returns:
            str: Job id
            dict: Results
        """
        # Flatten any arrays for JSON serialization
        if isinstance(geom, np.ndarray):
            geom = list(geom.flatten())

        job_options = options.copy()
        for key, value in job_options.items():
            if isinstance(value, np.ndarray):
                job_options[key] = list(value.flatten())
                
        # Package data according to API server specifications
        payload = {
            'api_key': self.api_key,
            'user_id': self.user,
            'geom': geom,
            'config': job_options,
        }

        # Send HTTP request
        try:
            r = requests.post(self.url + self.submit_endpoint, json=payload)
        except requests.exceptions.RequestError as e:
            raise HTTPCommunicationError('Error while POSTing for job submission', e)

        if r.status_code != requests.codes.ok:
            raise ServerError(r)

        response = json.loads(r.text)

        if self.verbose:
            print("SUBMIT> http code: {} response: {}".format(r.status_code, response))

        try:
            job_id = response['job_id']
        except KeyError:
            raise TCCError("Unexpectedly did not receive job ID: {}".format(response))

        return job_id

    def is_finished(self, results):
        """Helper function to test whether a job is finished.
        
        Args:
            results (dict): Job results from self.get_results()
        
        Returns:
            bool: True if job succeeded/failed, False if job is running/submitted/pending
        """
        job_status = results['job_status']
        return (job_status == 'SUCCESS' or job_status == 'FAILURE')

    def get_results(self, job_id):
        """Query API for results of calculations.

        Recommended way to check for job completion:
        ::

            results = client.get_results(job_id)
            finished = client.is_finished(results)

        Args:
            job_id (str): Job id to check status of

        Returns:
            dict: Result dictionary from TCC server with job_id added for posterity
        """
        payload = {
            'api_key': self.api_key,
            'user_id': self.user,
            'job_id': job_id
        }

        try:
            r = requests.get(self.url + self.results_endpoint, json=payload)
        except requests.exceptions.RequestError as e:
            raise HTTPCommunicationError('Error while GETing for job results', e)

        if r.status_code != requests.codes.ok:
            raise ServerError(r)

        results = json.loads(r.text)
        results['job_id'] = job_id

        if self.verbose:
            print("GET_RESULTS> job_id: {} current status: {}".format(
                job_id, results['job_status']))
            if self.is_finished(results):
                print(results)
        
        return results

    def poll_for_results(self, job_id, sleep_seconds=1, max_poll=200):
        """Send http request every sleep_seconds seconds until a finished job is
        returned or max_poll requests have been sent.

        Recommended way to check for job completion:
        ::

            results = client.poll_for_results(job_id)
            finished = client.is_finished(results)

        Args:
            job_id (str): Job id to poll for
            sleep_seconds (int): Number of seconds to wait between poll loops
            max_poll (int): Number of poll loops

        Returns:
            dict: Results dict as given by self.get_results()
        """
        results = {}
        for i in range(max_poll):
            if self.verbose:
                print('POLL_FOR_RESULTS> poll loop: {}'.format(i))

            results = self.get_results(job_id)
            if self.is_finished(results):
                break

            time.sleep(sleep_seconds)

        if self.verbose and not self.is_finished(results):
            print("!!!WARNING!!! {} did not finish during poll loop".format(job_id))

        return results

    def poll_for_bulk_results(self, job_ids, sleep_seconds=1, max_poll=200):
        """Send http request every sleep_seconds seconds until a finished job is
        returned or max_poll requests have been sent.

        Recommended way to check for job completion:
        ::

            results_list = client.poll_for_bulk_results(job_ids)
            finished = [client.is_finished(r) for r in results_list]

        Args:
            job_ids (list): Job ids to poll for
            sleep_seconds (int): Number of seconds to wait between poll loops
            max_poll (int): Number of poll loops

        Returns:
            list: List of results dicts as given by self.get_results()
        """
        # Initialize result storage
        results_dict = OrderedDict()
        for j in job_ids:
            results_dict[j] = {}

        running_jobs = list(results_dict.keys())
        for i in range(max_poll):
            if self.verbose:
                print('POLL_FOR_BULK_RESULTS> poll loop: {}'.format(i))

            for job_id in running_jobs:
                results_dict[job_id] = self.get_results(job_id)

            # Update running jobs
            running_jobs = [k for k,v in list(results_dict.items()) if not self.is_finished(v)]
            if len(running_jobs) == 0:
                break

            time.sleep(sleep_seconds)

        if self.verbose:
            for job_id in running_jobs:
                print("!!!WARNING!!! {} did not finish during poll loop".format(job_id))
    
        # Pull results out into list
        results_list = [v for v in results_dict.values()]

        return results_list

    def compute(self, geom, options, sleep_seconds=1, max_poll=200):
        """Convenience routine for synchronous use.

        Check self.poll_for_results() for recommended way to check for job completion.

        Args:
            geom ((num_atom, 3) ndarray): Geometry to consider
            options (dict): Job options to pass to TeraChem Cloud server
            sleep_seconds (int): Number of seconds to wait between poll loops for self.poll_for_results()
            max_poll (int): Number of poll loops for self.poll_for_results()
            **kwargs: TCC configuration passed to self.submit()

        Returns:
            dict: Job results from TCC server
        """
        job_id = self.submit(geom, options)

        results = self.poll_for_results(job_id, sleep_seconds, max_poll)

        return results

    def compute_bulk(self, geoms, options, sleep_seconds=1, max_poll=200):
        """Convenience routine for multiple geometries.

        Check self.poll_for_bulk_results() for recommended way to check for job completion.

        Args:
            geoms (list of (num_atom, 3) ndarray): Geometries to consider
            options (dict): Job options to pass to TeraChem Cloud server
            sleep_seconds (int): Number of seconds to wait between poll loops for self.poll_for_bulk_results()
            max_poll (int): Number of poll loops for self.poll_for_bulk_results()
            **kwargs: TCC configuration passed to self.submit()

        Returns:
            list: List of Job results from TCC server
        """
        job_ids = [self.submit(g, options) for g in geoms]

        results_list = self.poll_for_bulk_results(job_ids, sleep_seconds, max_poll)

        return results_list
        

