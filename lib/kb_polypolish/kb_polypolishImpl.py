# -*- coding: utf-8 -*-
#BEGIN_HEADER
import logging
import os
import re
import uuid
import json
import subprocess
import sys

from installed_clients.WorkspaceClient import Workspace
from installed_clients.ReadsUtilsClient import ReadsUtils
from installed_clients.KBaseReportClient import KBaseReport
from installed_clients.AssemblyUtilClient import AssemblyUtil
from installed_clients.DataFileUtilClient import DataFileUtil
#END_HEADER


class kb_polypolish:
    '''
    Module Name:
    kb_polypolish

    Module Description:
    A KBase module: kb_polypolish
    '''

    ######## WARNING FOR GEVENT USERS ####### noqa
    # Since asynchronous IO can lead to methods - even the same method -
    # interrupting each other, you must be *very* careful when using global
    # state. A method could easily clobber the state set by another while
    # the latter method is running.
    ######################################### noqa
    VERSION = "1.0.0"
    GIT_URL = "git@github.com:jmchandonia/kb_polypolish.git"
    GIT_COMMIT_HASH = "ca97c144a7d300bab7a13bea5aa0d0e075a5a8fc"

    #BEGIN_CLASS_HEADER
    def log(self, target, message):
        if target is not None:
            target.append(message)
        print(message)
        sys.stdout.flush()

    # get short reads, return separate forward and reverse files
    def download_short_reads(self, console, token, lib_ref):
        try:
            # download fwd/reverse in separate files
            ruClient = ReadsUtils(url=self.callbackURL, token=token)
            self.log(console, "Getting short reads.\n")
            result = ruClient.download_reads({'read_libraries': [lib_ref],
                                              'interleaved': 'false'})

            files = result['files'][lib_ref]['files']

            return files['fwd'], files['rev']

        except Exception as e:
            raise ValueError('Unable to download short reads\n' + str(e))

    # get assembly
    def download_assembly(self, console, token, lib_ref):
        try:
            auClient = AssemblyUtil(url=self.callbackURL, token=token)
            self.log(console, "Getting assembly.\n")
            result = auClient.get_assembly_as_fasta({
                'ref': lib_ref
            })

            return result['path']

        except Exception as e:
            raise ValueError('Unable to download assembly\n' + str(e))

    #END_CLASS_HEADER

    # config contains contents of config file in a hash or None if it couldn't
    # be found
    def __init__(self, config):
        #BEGIN_CONSTRUCTOR
        logging.basicConfig(format='%(created)s %(levelname)s: %(message)s',
                            level=logging.INFO)
        self.cfg = config
        self.cfg['SDK_CALLBACK_URL'] = os.environ['SDK_CALLBACK_URL']
        self.cfg['KB_AUTH_TOKEN'] = os.environ['KB_AUTH_TOKEN']
        self.callbackURL = self.cfg['SDK_CALLBACK_URL']
        self.workspaceURL = config['workspace-url']
        self.shockURL = config['shock-url']
        self.scratch = os.path.abspath(config['scratch'])
        if not os.path.exists(self.scratch):
            os.makedirs(self.scratch)
        #END_CONSTRUCTOR
        pass


    def run_kb_polypolish(self, ctx, params):
        """
        This example function accepts any number of parameters and returns results in a KBaseReport
        :param params: instance of mapping from String to unspecified object
        :returns: instance of type "ReportResults" -> structure: parameter
           "report_name" of String, parameter "report_ref" of String
        """
        # ctx is the context object
        # return variables are: output
        #BEGIN run_kb_polypolish
        console = []
        # self.log(console, 'Running run_kb_polypolish with params:\n{}'.format(
        #     json.dumps(params, indent=1)))
        token = self.cfg['KB_AUTH_TOKEN']

        # param checks
        required_params = ['workspace_name',
                           'input_reads_library',
                           'output_assembly',
                           'input_assembly']
        for required_param in required_params:
            if required_param not in params or params[required_param] is None:
                raise ValueError("Must define required param: '"+required_param+"'")

        # load provenance
        provenance = [{}]
        if 'provenance' in ctx:
            provenance = ctx['provenance']
        if 'input_ws_objects' not in provenance[0]:
            provenance[0]['input_ws_objects'] = []
        if 'input_reads_library' in params and params['input_reads_library'] is not None:
            provenance[0]['input_ws_objects'].append(params['input_reads_library'])
        if 'input_assembly' in params and params['input_assembly'] is not None:
            provenance[0]['input_ws_objects'].append(params['input_assembly'])

        # download all inputs
        short1, short2 = self.download_short_reads(
            console, token, params['input_reads_library'])

        draft = self.download_assembly(
            console, token, params['input_assembly'])

        # index assembly
        cmd = 'bwa index '+draft
        self.log(console, "command: "+cmd)
        cmdProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, shell=True)
        for line in cmdProcess.stdout:
            self.log(console, line.decode("utf-8").rstrip())
        cmdProcess.wait()
        if cmdProcess.returncode != 0:
            raise ValueError('Error running '+cmd)

        # map all short reads
        sam1 = os.path.join(self.scratch, "alignments1_"+str(uuid.uuid4())+".sam")
        cmd = 'bwa mem -a -k1 -T7 -A1 -B1 -O1 -E1 -L100 '+draft+' '+short1+' > '+sam1
        self.log(console, "command: "+cmd)
        cmdProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, shell=True)
        for line in cmdProcess.stdout:
            self.log(console, line.decode("utf-8").rstrip())
        cmdProcess.wait()
        if cmdProcess.returncode != 0:
            raise ValueError('Error running '+cmd)

        sam2 = None
        if short2 is not None:
            sam2 = os.path.join(self.scratch, "alignments2_"+str(uuid.uuid4())+".sam")
            cmd = 'bwa mem -a -k1 -T7 -A1 -B1 -O1 -E1 -L100 '+draft+' '+short2+' > '+sam2
            self.log(console, "command: "+cmd)
            cmdProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, shell=True)
            for line in cmdProcess.stdout:
                self.log(console, line.decode("utf-8").rstrip())
                cmdProcess.wait()
                if cmdProcess.returncode != 0:
                    raise ValueError('Error running '+cmd)

        # insert filter, only if we have paired reads
        if sam2 is not None:
            filt1 = os.path.join(self.scratch, "filtered1_"+str(uuid.uuid4())+".sam")
            filt2 = os.path.join(self.scratch, "filtered2_"+str(uuid.uuid4())+".sam")
            cmd = 'polypolish filter --in1 '+sam1+' --in2 '+sam2+' --out1 '+filt1+' --out2 '+filt2
            self.log(console, "command: "+cmd)
            cmdProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, shell=True)
            for line in cmdProcess.stdout:
                self.log(console, line.decode("utf-8").rstrip())
                cmdProcess.wait()
                if cmdProcess.returncode != 0:
                    raise ValueError('Error running '+cmd)

        # build command line
        cmd = 'polypolish polish'

        if 'fraction_invalid' in params and params['fraction_invalid'] is not None:
            cmd += ' --fraction_invalid '+str(params['fraction_invalid'])

        if 'fraction_valid' in params and params['fraction_valid'] is not None:
            cmd += ' --fraction_valid '+str(params['fraction_valid'])

        if 'max_errors' in params and params['max_errors'] is not None:
            cmd += ' --max_errors '+str(params['max_errors'])

        if 'min_depth' in params and params['min_depth'] is not None:
            cmd += ' --min_depth '+str(params['min_depth'])

        cmd += ' '+draft

        if short2 is None:
            cmd += ' '+sam1
        else:
            cmd += ' '+filt1+' '+filt2

        # output file
        outputFile = os.path.join(self.scratch, "polypolish_output_"+str(uuid.uuid4())+".fasta")
        cmd += ' > '+outputFile

        # run it
        self.log(console, "command: "+cmd)
        cmdProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, shell=True)
        for line in cmdProcess.stdout:
            self.log(console, line.decode("utf-8").rstrip())
            cmdProcess.wait()
            if cmdProcess.returncode != 0:
                raise ValueError('Error running '+cmd)

        # save assembly
        auClient = AssemblyUtil(url=self.callbackURL, token=token)
        obj_ref = auClient.save_assembly_from_fasta({
            'file': {'path': outputFile},
            'workspace_name': params['workspace_name'],
            'assembly_name': params['output_assembly']
        })

        # build report
        self.log(console, 'Generating and saving report.')

        report_text = '\n'.join(console)
        report_text += '\nPolypolish results saved.\n'
        
        reportClient = KBaseReport(self.callbackURL)
        report_output = reportClient.create_extended_report(
            {'message': report_text,
             'objects_created': [{'ref': obj_ref, 'description': 'Polished assembly'}],
             'report_object_name': 'kb_polypolish_report_' + str(uuid.uuid4()),
             'workspace_name': params['workspace_name']})
             
        output = {
            'report_name': report_output['name'],
            'report_ref': report_output['ref'],
        }
        #END run_kb_polypolish

        # At some point might do deeper type checking...
        if not isinstance(output, dict):
            raise ValueError('Method run_kb_polypolish return value ' +
                             'output is not type dict as required.')
        # return the results
        return [output]
    def status(self, ctx):
        #BEGIN_STATUS
        returnVal = {'state': "OK",
                     'message': "",
                     'version': self.VERSION,
                     'git_url': self.GIT_URL,
                     'git_commit_hash': self.GIT_COMMIT_HASH}
        #END_STATUS
        return [returnVal]
