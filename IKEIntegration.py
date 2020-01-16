import onevizion
import requests
from requests.auth import HTTPBasicAuth
import os
import re
import json
from datetime import datetime, timedelta

class Integration():
    
    def __init__(self, process_id = "", url_onevizion="", login_onevizion="", pass_onevizion="", url_ike="", login_ike="", pass_ike=""):
        self.url_onevizion = self.url_setting(url_onevizion)
        self.login_onevizion = login_onevizion
        self.pass_onevizion = pass_onevizion
        self.auth_onevizion = HTTPBasicAuth(login_onevizion, pass_onevizion)

        self.url_ike = self.url_setting(url_ike)
        self.login_ike = login_ike
        self.pass_ike = pass_ike

        self.fm_list_request = onevizion.Trackor(trackorType='ike_field_mapping', URL=self.url_onevizion, userName=login_onevizion, password=pass_onevizion)

        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.process_id = process_id

        self.start_integration()

    def start_integration(self):
        self.create_log('Info', 'Started integration')

        self.ike_token = self.get_ike_token()['token']
        recieved_trackor_types = self.get_trackor_types()

        form_id_list = []
        revieved_field_mapping = self.get_field_mapping()
        for form in revieved_field_mapping:
            if form['IFM_IKE_FORM_ID'] not in form_id_list:
                form_id_list.append(form['IFM_IKE_FORM_ID'])

        field_list = []
        for ike_job in self.get_ike_job():
            candidate_letter = re.split('_',ike_job['candidate_name'])
            candidate_letter = candidate_letter[len(candidate_letter)-1]
            
            ike_collections = self.get_ike_collection(ike_job['department_id'], ike_job['job_id'])
            ike_form_id = ike_collections[0]['form']['id']
            if ike_form_id in form_id_list:
                for ike_collection in ike_collections:
                    for collect in ike_collection['fields']:
                        if re.search('Candidate Name', collect['name']) is not None:
                            inf_value = collect['value']
                            break

                    letter_search = re.search(r'^[A-Z]|[a-z]$',inf_value)
                    if letter_search is None:
                        self.create_log('Warning', 'Incorrect candidate name specified - ' + inf_value + ' - for Job - ' + ike_job['candidate_name'])
                    elif letter_search is not None and inf_value == candidate_letter:
                        for field_mapping in revieved_field_mapping:
                            inf_value = None
                            inf_v = ''
                            inf_name_id = None
                            ike_name_id = None
                            ike_field = field_mapping['IFM_IKE_FIELD_NAME']
                            for collect in ike_collection['fields']:
                                if re.search(ike_field, collect['field']) is not None:
                                    if collect['value'] != None:
                                        if isinstance(collect['value'], float) == True or isinstance(collect['value'], bool) == True:
                                            inf_v = str(collect['value'])
                                        else:
                                            inf_v = collect['value']
                                else:
                                    ike_name_value = collect['value']
                                    if isinstance(ike_name_value, list) and len(ike_name_value) > 0:
                                        if 'fields' in ike_name_value[0]:
                                            ike_name_vf = ike_name_value[0]['fields']
                                            if isinstance(ike_name_vf, list) and len(ike_name_vf) > 0:
                                                if 'field' in ike_name_vf[0]:
                                                    for inf in ike_name_vf:
                                                        if re.search(ike_field, inf['field']) is not None:
                                                            if inf['value'] != None:
                                                                ike_name_id = ike_name_value[0]['id']
                                                                if isinstance(inf['value'], float) == True or isinstance(inf['value'], bool) == True:
                                                                    inf_v = str(inf['value'])
                                                                else:
                                                                    inf_v = inf['value']
                                                                break
                                                        else:
                                                            inf_name_value = inf['value']
                                                            if isinstance(inf_name_value, list) and len(inf_name_value) > 0:
                                                                if 'fields' in inf_name_value[0]:
                                                                    inf_name_vf = inf_name_value[0]['fields']
                                                                    if isinstance(inf_name_vf, list) and len(inf_name_vf) > 0:
                                                                        if 'field' in inf_name_vf[0]:
                                                                            for inv in inf_name_vf:
                                                                                if re.search(ike_field, inv['field']) is not None:
                                                                                    if inv['value'] != None:
                                                                                        inf_name_id = ike_name_value[0]['id']
                                                                                        if isinstance(inv['value'], float) == True or isinstance(inv['value'], bool) == True:
                                                                                            inf_v = str(inv['value'])
                                                                                        else:
                                                                                            inf_v = inv['value']
                                                                                    break
                                if len(inf_v) > 0:
                                    if 'location' in ike_field and '_LONG' in field_mapping['IFM_ESPEED_FIELD_NAME'] and 'longitude' in inf_v:
                                        inf_value = str(inf_v['longitude'])
                                    elif 'location' in ike_field and '_LAT' in field_mapping['IFM_ESPEED_FIELD_NAME'] and 'latitude' in inf_v:
                                        inf_value = str(inf_v['latitude'])
                                    elif 'nestedlist' in ike_field and len(inf_v) > 0:
                                        for title in inf_v:
                                            if 'Pole Owner' in title['title']:
                                                inf_value = title['value']
                                                break
                                    elif 'selectlist' in ike_field and 'title' in inf_v:
                                        if inf_v['value'] != 'unselected':
                                            inf_value = inf_v['title']
                                        else:
                                            inf_value = None
                                    elif 'vector' in ike_field and 'distance' in inf_v:
                                        inf_value = str(float(inf_v['distance']) / .3048)
                                    elif 'image' in ike_field and len(inf_v) > 0:
                                        inf_value = self.get_ike_image(inf_v[0], ike_collection['captures'])
                                    elif 'truesizecapture' in ike_field and len(inf_v) > 0:
                                        inf_value = self.get_ike_image(inf_v[0], ike_collection['captures'])
                                    elif 'height' in ike_field and inf_v != None:
                                        inf_value = str(float(inf_v) / .3048)
                                    else: inf_value = inf_v

                                if inf_value != None and 'IKE_image' in inf_value:
                                    field_list.append({'ike_id':'', 'trackor_type':'IKE_image.' + field_mapping['IFM_ESPEED_FIELD_NAME'], 'field_value':re.split('IKE_image.', inf_value)[1]})
                                    break
                                elif inf_value != None and 'IKE_image' not in inf_value:
                                    for trackor_types in recieved_trackor_types:
                                        if re.search(field_mapping['IFM_FIELD_TRACKOR_TYPE'], trackor_types['label']) is not None:
                                            trackor_type = trackor_types['name']
                                            break
                                    
                                    if inf_name_id != None:
                                        field_list.append({'ike_id':inf_name_id, 'trackor_type':trackor_type + '.' + field_mapping['IFM_ESPEED_FIELD_NAME'], 'field_value':inf_value})
                                    elif ike_name_id != None:
                                        field_list.append({'ike_id':ike_name_id, 'trackor_type':trackor_type + '.' + field_mapping['IFM_ESPEED_FIELD_NAME'], 'field_value':inf_value})
                                    else:
                                        field_list.append({'ike_id':'', 'trackor_type':trackor_type + '.' + field_mapping['IFM_ESPEED_FIELD_NAME'], 'field_value':inf_value})
                                    break
                                inf_v = ''
                                inf_value = None
                        if len(field_list) > 0:
                            field_list.append({'ike_id':'', 'trackor_type':'Candidate.TRACKOR_KEY', 'field_value':ike_job['candidate_id']})
                            field_list.append({'ike_id':'', 'trackor_type':'IKE_Checklists.IKE_UPDATED_AT', 'field_value':ike_job['updatedAt']})
                            self.work_with_checklists(field_list)
                            field_list.clear()
                        else:
                            self.create_log('Warning', 'No data / failed to select data for Job - ' + ike_job['candidate_name'])

                        filelist = [f for f in os.listdir() if f.endswith('.jpeg')]
                        for f in filelist:
                            os.remove(os.path.join(f))
                    else:
                        self.create_log('Warning', 'No candidates on espeed for Job - ' + ike_job['candidate_name'] + ' - with candidate name - ' + inf_value)

        self.create_log('Info', 'Finished integration')

    def get_ike_job(self):
        for deprtment in self.get_ike_department():
            department_id = deprtment['id']

            url = 'https://' + self.url_ike + '/v1/job.json'
            data = {'departmentId':department_id}
            answer = requests.get(url, headers={'Content-type':'application/json', 'Authorization':'token ' + self.ike_token}, params=data)

            ike_job_list = []
            for job in answer.json():
                ike_job_list.append({'job_name':job['name'], 'job_id':job['id'], 'job_updatedAt':job['updatedAt']})

            candidate_names = self.check_candidate_name(ike_job_list)

            job_list = []
            for jl in ike_job_list:
                jl_in_cn = 0
                for cn in candidate_names:
                    job_updated = datetime.strptime(jl['job_updatedAt'], '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%dT%H:%M:%S')
                    if jl['job_name'] in cn['C_CANDIDATE_NAME'] and (job_updated != cn['IKE_Checklists.IKE_UPDATED_AT'] or cn['IKE_Checklists.IKE_UPDATED_AT'] == None):
                        job_list.append({'candidate_id':cn['TRACKOR_KEY'], 'candidate_name':cn['C_CANDIDATE_NAME'], 'updatedAt':job_updated, 'department_id':department_id, 'job_id':jl['job_id']})
                        jl_in_cn = 1
                        break
                if jl_in_cn == 0:
                    self.create_log('Warning', 'Job - ' + jl['job_name'] + ' - missing in espeed')
        ike_job_list.clear()

        return job_list

    def get_ike_token(self):
        url = 'https://' + self.url_ike + '/v1/login'
        data = {'username':self.login_ike, 'password':self.pass_ike}
        answer = requests.post(url, data=json.dumps(data), headers={'Content-type':'application/json'})
        response = answer.json()
        return response

    def get_ike_department(self):
        url = 'https://' + self.url_ike + '/v1/department.json'
        answer = requests.get(url, headers={'Content-type':'application/json', 'Authorization':'token ' + self.ike_token})
        response = answer.json()
        return response

    def get_ike_collection(self, department_id, job_id):
        url = 'https://' + self.url_ike + '/v1/collection.json'
        data = {'departmentId':department_id, 'jobId':job_id}
        answer = requests.get(url, headers={'Content-type':'application/json', 'Authorization':'token ' + self.ike_token}, params=data)
        response = answer.json()
        return response

    def check_candidate_name(self, ike_job_list):
        i = 0
        jobs_name = ''
        candidate_list = []
        len_ike_job_list = len(ike_job_list)
        for job_name in ike_job_list:
            if len_ike_job_list > 150:
                jobs_name = job_name['job_name'] + ',' + jobs_name
                i = i + 1
            else:
                jobs_name = job_name['job_name'] + ',' + jobs_name
            
            if i == 150:
                url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/site/trackors'
                data = {'fields':'S_PRIMARY_CANDIDATE', 'S_SITE_NAME':jobs_name[:-1]}
                answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
                if answer.status_code != 200:
                    self.create_log('Warning', answer.text)
                else:
                    response = answer.json()
                    for resp in response:
                        if resp['S_PRIMARY_CANDIDATE'] != None:
                            candidate_list.append({'primary_candidate':resp['S_PRIMARY_CANDIDATE']})
                i = 0
                jobs_name = ''
                len_ike_job_list = len_ike_job_list - 150
        
        if jobs_name != '':
            url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/site/trackors'
            data = {'fields':'S_PRIMARY_CANDIDATE', 'S_SITE_NAME':jobs_name[:-1]}
            answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
            if answer.status_code != 200:
                self.create_log('Warning', answer.text)
            else:
                response = answer.json()
                for resp in response:
                    if resp['S_PRIMARY_CANDIDATE'] != None:
                        candidate_list.append({'primary_candidate':resp['S_PRIMARY_CANDIDATE']})

        j = 0
        sites_name = ''
        job_list = []
        len_ike_candidate_list = len(candidate_list)
        for ike_cl in candidate_list:
            if len_ike_candidate_list > 150:
                sites_name = ike_cl['primary_candidate'] + ',' + sites_name
                j = j + 1
            else:
                sites_name = ike_cl['primary_candidate'] + ',' + sites_name

            if j == 150:
                url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/candidate/trackors'
                data = {'fields':'TRACKOR_KEY, C_CANDIDATE_NAME, IKE_Checklists.IKE_UPDATED_AT', 'C_CANDIDATE_NAME':sites_name[:-1]}
                answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
                if answer.status_code != 200:
                    self.create_log('Warning', answer.text)
                else:
                    response = answer.json()
                    for resp in response:
                        job_list.append({'TRACKOR_KEY':resp['TRACKOR_KEY'], 'C_CANDIDATE_NAME':resp['C_CANDIDATE_NAME'], 'IKE_Checklists.IKE_UPDATED_AT':resp['IKE_Checklists.IKE_UPDATED_AT']})

                j = 0
                sites_name = ''
                len_ike_candidate_list = len_ike_candidate_list - 150

        if sites_name != '':
                url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/candidate/trackors'
                data = {'fields':'TRACKOR_KEY, C_CANDIDATE_NAME, IKE_Checklists.IKE_UPDATED_AT', 'C_CANDIDATE_NAME':sites_name[:-1]}
                answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
                if answer.status_code != 200:
                    self.create_log('Warning', answer.text)
                else:
                    response = answer.json()
                    for resp in response:
                        job_list.append({'TRACKOR_KEY':resp['TRACKOR_KEY'], 'C_CANDIDATE_NAME':resp['C_CANDIDATE_NAME'], 'IKE_Checklists.IKE_UPDATED_AT':resp['IKE_Checklists.IKE_UPDATED_AT']})

        candidate_list.clear()
        return job_list

    def get_ike_image(self, inf_v, captures):
        for collect in captures:
            if re.search(inf_v, collect['id']) is not None and collect['type'] == 'image':
                inf_value = collect['imageUrl']
                break
            elif re.search(inf_v, collect['id']) is not None and collect['type'] == 'truesize':
                inf_value = collect['compositeUrl']
                break

        if len(inf_value) > 0:
            image_name = re.split('/',inf_value)
            image_name = image_name[len(image_name)-1]
            image = requests.get(inf_value, headers={'Accept':'application/json'})
            img_file = open(image_name, 'wb')
            img_file.write(image.content)
            img_file.close

            return 'IKE_image.' + image_name
        else:
            return None

    def get_field_mapping(self):
        self.fm_list_request.read(
                fields=['IFM_FIELD_TRACKOR_TYPE', 'IFM_ESPEED_FIELD_NAME', 'IFM_IKE_FIELD_NAME', 'IFM_IKE_FORM_ID']
                )
        response = self.fm_list_request.jsonData

        fm_list = []
        for field_mapping in response:
            fm_list.append(field_mapping)

        return fm_list

    def get_trackor_types(self):
        url = 'https://' + self.url_onevizion + '/api/v3/trackor_types'
        answer = requests.get(url, headers=self.headers, auth=self.auth_onevizion)
        if answer.status_code != 200:
            self.create_log('Warning', answer.text)
        else:
            return answer.json()

    def work_with_checklists(self, field_list):
        candidate_id = 0
        candidate_name = None
        for field_data in field_list:
            if re.search('Candidate.TRACKOR_KEY', field_data['trackor_type']) is not None:
                data_checklists = self.get_checklist(field_data['field_value'])
                if len(data_checklists) > 0:
                    candidate_id = data_checklists[0]['TRACKOR_ID']
                    candidate_name = data_checklists[0]['TRACKOR_KEY']
                break

        checklists_dict = {}
        candidate_dict = {}
        placement_id = ''
        placement_list = []
        anchors_id = ''
        anchors_list = []
        span_id = ''
        spans_list = []
        equipment_id = ''
        equipment_list = []
        image_list = []
        for field_data in field_list:
            if 'IKE_Checklists' in field_data['trackor_type']:
                checklists_dict[re.split('IKE_Checklists.', field_data['trackor_type'])[1]] = field_data['field_value']
            elif 'Candidate' in field_data['trackor_type']:
                candidate_dict[field_data['trackor_type']] = field_data['field_value']
            elif 'IKE_POLE_PLACEMENT' in field_data['trackor_type']:
                if len(placement_list) > 0:
                    for pl in placement_list:
                        if field_data['ike_id'] == pl['ike_id']:
                            pl.update({'ike_id':field_data['ike_id'], re.split('IKE_POLE_PLACEMENT.', field_data['trackor_type'])[1]:field_data['field_value']})
                            placement_id = field_data['ike_id']
                            break
                    if placement_id == '':
                        placement_list.append({'ike_id':field_data['ike_id'], re.split('IKE_POLE_PLACEMENT.', field_data['trackor_type'])[1]:field_data['field_value']})
                else:
                    placement_list.append({'ike_id':field_data['ike_id'], re.split('IKE_POLE_PLACEMENT.', field_data['trackor_type'])[1]:field_data['field_value']})
                    placement_id = field_data['ike_id']
            elif 'IKE_ANCHORS' in field_data['trackor_type']:
                if len(anchors_list) > 0:
                    for al in anchors_list:
                        if field_data['ike_id'] == al['ike_id']:
                            al.update({'ike_id':field_data['ike_id'], re.split('IKE_ANCHORS.', field_data['trackor_type'])[1]:field_data['field_value']})
                            anchors_id = field_data['ike_id']
                            break
                    if anchors_id == '':
                        anchors_list.append({'ike_id':field_data['ike_id'], re.split('IKE_ANCHORS.', field_data['trackor_type'])[1]:field_data['field_value']})
                else:
                    anchors_list.append({'ike_id':field_data['ike_id'], re.split('IKE_ANCHORS.', field_data['trackor_type'])[1]:field_data['field_value']})
                    anchors_id = field_data['ike_id']
            elif 'IKE_Span' in field_data['trackor_type']:
                if len(spans_list) > 0:
                    for sl in spans_list:
                        if field_data['ike_id'] == sl['ike_id']:
                            sl.update({'ike_id':field_data['ike_id'], re.split('IKE_Span.', field_data['trackor_type'])[1]:field_data['field_value']})
                            span_id = field_data['ike_id']
                            break
                    if span_id == '':
                        spans_list.append({'ike_id':field_data['ike_id'], re.split('IKE_Span.', field_data['trackor_type'])[1]:field_data['field_value']})
                else:
                    spans_list.append({'ike_id':field_data['ike_id'], re.split('IKE_Span.', field_data['trackor_type'])[1]:field_data['field_value']})
                    span_id = field_data['ike_id']
            elif 'IKE_EQUIPMENT' in field_data['trackor_type']:
                if len(equipment_list) > 0:
                    for el in equipment_list:
                        if field_data['ike_id'] == el['ike_id']:
                            el.update({'ike_id':field_data['ike_id'], re.split('IKE_EQUIPMENT.', field_data['trackor_type'])[1]:field_data['field_value']})
                            equipment_id = field_data['ike_id']
                            break
                    if equipment_id == '':
                        equipment_list.append({'ike_id':field_data['ike_id'], re.split('IKE_EQUIPMENT.', field_data['trackor_type'])[1]:field_data['field_value']})
                else:
                    equipment_list.append({'ike_id':field_data['ike_id'], re.split('IKE_EQUIPMENT.', field_data['trackor_type'])[1]:field_data['field_value']})
                    equipment_id = field_data['ike_id']
            elif 'IKE_image' in field_data['trackor_type']:
                image_list.append({'trackor_type':re.split('IKE_image.', field_data['trackor_type'])[1], 'file_name':field_data['field_value']})

        if len(checklists_dict) > 0 and len(candidate_dict) > 0 and candidate_id == 0 and candidate_name == None:
            url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_Checklists/trackors'
            data = {'fields':checklists_dict, 'parents':[{'trackor_type':'Candidate', 'filter':candidate_dict}]}
            answer = requests.post(url, data=json.dumps(data), headers={'Accept':'application/json'}, auth=self.auth_onevizion)
            if answer.status_code != 201:
                self.create_log('Warning', str(candidate_dict['Candidate.TRACKOR_KEY']) + ' - ' +  answer.text)
            else:
                candidate_id = answer.json()['TRACKOR_ID']
                candidate_name = answer.json()['TRACKOR_KEY']
                candidate_dict.clear()

        if candidate_id != 0:
            if len(checklists_dict) > 0: 
                url = 'https://' + self.url_onevizion + '/api/v3/trackors/' + str(candidate_id)
                data = checklists_dict
                answer = requests.put(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
                if answer.status_code != 200:
                    self.create_log('Warning', answer.text)
                
                checklists_dict.clear()

            if len(image_list) > 0:
                for image_file in image_list:
                    url = 'https://' + self.url_onevizion + '/api/v3/trackor/' + str(candidate_id) + '/file/' + image_file['trackor_type']
                    data = {'file_name':image_file['file_name']}
                    files = {'file':(image_file['file_name'], open(image_file['file_name'], 'rb'))}
                    answer = requests.post(url, files=files, params=data, headers={'Accept':'application/json'}, auth=self.auth_onevizion)
                    if answer.status_code != 200:
                        self.create_log('Warning', answer.text)
                    
                image_list.clear()

        if candidate_name != None:                    
            if len(placement_list) > 0:
                for pl in placement_list:
                    pl.pop('ike_id', None)
                    url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_POLE_PLACEMENT/trackors'
                    data = {'fields':pl, 'parents':[{'trackor_type':'IKE_Checklists', 'filter':{'TRACKOR_KEY':candidate_name}}]}
                    answer = requests.post(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
                    if answer.status_code != 201:
                        self.create_log('Warning', answer.text)

                placement_list.clear()

            if len(anchors_list) > 0:
                for al in anchors_list:
                    al.pop('ike_id', None)
                    url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_ANCHORS/trackors'
                    data = {'fields':al, 'parents':[{'trackor_type':'IKE_Checklists', 'filter':{'TRACKOR_KEY':candidate_name}}]}
                    answer = requests.post(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
                    if answer.status_code != 201:
                        self.create_log('Warning', answer.text)

                anchors_list.clear()

            if len(spans_list) > 0:
                for sl in spans_list:
                    sl.pop('ike_id', None)
                    url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_Span/trackors'
                    data = {'fields':sl, 'parents':[{'trackor_type':'IKE_Checklists', 'filter':{'TRACKOR_KEY':candidate_name}}]}
                    answer = requests.post(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
                    if answer.status_code != 201:
                        self.create_log('Warning', answer.text)

                spans_list.clear()

            if len(equipment_list) > 0:
                for el in equipment_list:
                    el.pop('ike_id', None)
                    url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_EQUIPMENT/trackors'
                    data = {'fields':el, 'parents':[{'trackor_type':'IKE_Checklists', 'filter':{'TRACKOR_KEY':candidate_name}}]}
                    requests.post(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
                    if answer.status_code != 201:
                        self.create_log('Warning', answer.text)

                equipment_list.clear()

    def get_checklist(self, candidate_id):
        url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_Checklists/trackors'
        data = {'Candidate.TRACKOR_KEY':candidate_id}
        answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
        if answer.status_code != 200:
            self.create_log('Warning', answer.text)
        else:
            return answer.json()

    def create_log(self, log_level_name, message_log):
        url = 'https://' + self.url_onevizion + '/api/v3/integrations/runs/' + str(self.process_id) + '/logs'
        data = {'message':message_log, 'log_level_name':log_level_name}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_onevizion)

    def url_setting(self, url):
        url_re_start = re.search('^https', url)
        url_re_finish = re.search('/$', url)
        if url_re_start is not None and url_re_finish is not None:
            url_split = re.split('://',url[:-1],2)
            url = url_split[1]  
        elif url_re_start is None and url_re_finish is not None:
            url = url[:-1]
        elif url_re_start is not None and url_re_finish is None:
            url_split = re.split('://',url,2)
            url = url_split[1]
        return url