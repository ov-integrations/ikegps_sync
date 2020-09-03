import onevizion
import requests
from requests.auth import HTTPBasicAuth
import os
import re
import json
from datetime import datetime, timedelta

class Integration():
    LEN_CANDIDATE_NAME_LIST = 150

    def __init__(self, url_onevizion="", login_onevizion="", pass_onevizion="", url_ike="", login_ike="", pass_ike=""):
        self.url_onevizion = self.url_setting(url_onevizion)
        self.auth_onevizion = HTTPBasicAuth(login_onevizion, pass_onevizion)

        self.url_ike = self.url_setting(url_ike)
        self.login_ike = login_ike
        self.pass_ike = pass_ike

        self.fm_list_request = onevizion.Trackor(trackorType='ike_field_mapping', URL=self.url_onevizion, userName=login_onevizion, password=pass_onevizion)

        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.log = onevizion.TraceMessage

    def start_integration(self):
        self.log('Starting integration')
        fields_mapping = self.get_fields_mapping()
        ike_candidates_data = self.prepare_ike_candidates_data(fields_mapping)
        if ike_candidates_data is not None:
            self.parse_ike_candidates_data(ike_candidates_data, fields_mapping)
        self.log('Integration has been completed')

    def prepare_ike_candidates_data(self, fields_mapping):
        try:
            self.ike_token = self.get_ike_token()
        except Exception as e:
            self.log('Failed to get_ike_token. Exception[%s]' % str(e))
            raise SystemExit('Failed to get_ike_token. Exception[%s]' % str(e))

        try:
            department_list = self.get_ike_department()
        except Exception as e:
            self.log('Failed to get_ike_department. Exception[%s]' % str(e))
            raise SystemExit('Failed to get_ike_department. Exception[%s]' % str(e))

        ike_job_list = self.get_ike_job_list(department_list)
        ike_collection_list = self.get_ike_collection_list(ike_job_list, fields_mapping)
        ike_candidates_list = self.get_ike_candidates_list(ike_collection_list)

        return ike_candidates_list

    def get_ike_token(self):
        url = 'https://' + self.url_ike + '/v1/login'
        data = {'username':self.login_ike, 'password':self.pass_ike}
        answer = requests.post(url, data=json.dumps(data), headers={'Content-type':'application/json'})
        if answer.ok:
            return answer.json()['token']
        else:
            raise Exception(answer.text)

    def get_ike_department(self):
        url = 'https://' + self.url_ike + '/v1/department.json'
        answer = requests.get(url, headers={'Content-type':'application/json', 'Authorization':'token ' + self.ike_token})
        if answer.ok:
            return answer.json()
        else:
            raise Exception(answer.text)

    def get_ike_job_list(self, department_list):
        previous_week = str((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S'))
        for department in department_list:
            department_id = department['id']

            try:
                job_list = self.get_job_list(department_id)
            except Exception as e:
                self.log('Failed to get_job_list. Exception [%s]' % str(e))
                raise SystemExit('Failed to get_job_list. Exception [%s]' % str(e))

            ike_job_list = []
            for job in job_list:
                if job['updatedAt'] > previous_week:
                    ike_job_list.append({'job_id':job['id'], 'job_name':job['name'], 'department_id':department_id})

        return ike_job_list

    def get_job_list(self, department_id):
        url = 'https://' + self.url_ike + '/v1/job.json'
        data = {'departmentId':department_id}
        answer = requests.get(url, headers={'Content-type':'application/json', 'Authorization':'token ' + self.ike_token}, params=data)
        if answer.ok:
            return answer.json()
        else:
            raise Exception(answer.text)

    def get_ike_collection_list(self, ike_job_list, fields_mapping):
        ike_collections_list = []
        incorrect_name_list = []
        
        form_id_list = []
        for field_mapping in fields_mapping:
            if field_mapping['IFM_IKE_FORM_ID'] not in form_id_list:
                form_id_list.append(field_mapping['IFM_IKE_FORM_ID'])

        for ike_job in ike_job_list:
            try:
                collection_list = self.get_collection_list(ike_job['department_id'], ike_job['job_id'])
            except Exception as e:
                self.log('Failed to get_collection_list. Exception [%s]' % str(e))
                raise SystemExit('Failed to get_collection_list. Exception [%s]' % str(e))

            for ike_collection in collection_list:
                if ike_collection['form']['id'] not in form_id_list:
                    continue
                for collect in ike_collection['fields']:
                    if re.search('Candidate Name', collect['name']) is not None:
                        if len(collect['value']) == 1:
                            if re.search(r'^[A-Z]|[a-z]$', collect['value']) is None:
                                incorrect_name_list.append('Incorrect candidate name specified - ' + collect['value'] + ' - for Job - ' + ike_job['job_name'])
                            else:
                                job_updated = datetime.strptime(re.split(r'\.', ike_collection['updatedAt'])[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%dT%H:%M:%S')
                                inf_value = ike_job['job_name'] + '_' + collect['value'].title()
                                ike_collections_list.append({'candidate_name':inf_value, 'job_updated':job_updated, 'ike_collection':ike_collection})
                        else:
                            incorrect_name_list.append('Incorrect candidate name specified - ' + collect['value'] + ' - for Job - ' + ike_job['job_name'])
                        break

        if len(incorrect_name_list) > 0:
            self.log(incorrect_name_list)
        return ike_collections_list

    def get_collection_list(self, department_id, job_id):
        url = 'https://' + self.url_ike + '/v1/collection.json'
        data = {'departmentId':department_id, 'jobId':job_id}
        answer = requests.get(url, headers={'Content-type':'application/json', 'Authorization':'token ' + self.ike_token}, params=data)
        if answer.ok:
            return answer.json()
        else:
            raise Exception(answer.text)

    def get_ike_candidates_list(self, ike_collection_list):
        candidate_list = []
        candidate_name_list = []
        len_ike_collection_list = len(ike_collection_list)
        for collection in ike_collection_list:
            candidate_name_list.append(collection['candidate_name'])

            if len_ike_collection_list < Integration.LEN_CANDIDATE_NAME_LIST:
                if len(candidate_name_list) == len_ike_collection_list:
                    candidate_list.extend(self.work_with_candidates(candidate_name_list))
                    candidate_name_list.clear()
            else:
                if len(candidate_name_list) == Integration.LEN_CANDIDATE_NAME_LIST:
                    candidate_list.extend(self.work_with_candidates(candidate_name_list))
                    candidate_name_list.clear()
                    len_ike_collection_list = len_ike_collection_list - Integration.LEN_CANDIDATE_NAME_LIST

        ike_candidate_list = []
        candidate_missing_list = []
        for collection in ike_collection_list:
            j = 0
            for candidate in candidate_list:
                if candidate['C_CANDIDATE_NAME'] in collection['candidate_name']:
                    if candidate['IKE_Checklists.IKE_UPDATED_AT'] != collection['job_updated']:
                        ike_candidate_list.append({'TRACKOR_KEY':candidate['TRACKOR_KEY'], 'C_CANDIDATE_NAME':candidate['C_CANDIDATE_NAME'], 'IKE_Checklists.IKE_UPDATED_AT':collection['job_updated'], 'ike_collection':collection['ike_collection']})
                    j = 1
                    break
            if j == 0:
                candidate_missing_list.append('Candidate - ' + collection['candidate_name'] + ' - missing in espeed')

        if len(candidate_missing_list) > 0:
            self.log(candidate_missing_list)

        if len(ike_candidate_list) > 0:
            return ike_candidate_list
        else:
            return None

    def work_with_candidates(self, candidate_name_list):
        candidate_list = []
        try:
            cadidates = self.get_candidates(candidate_name_list)
        except Exception as e:
            self.log('Failed to get_candidates. Exception [%s]' % str(e))
            raise SystemExit('Failed to get_candidates. Exception [%s]' % str(e))

        for candidate in cadidates:
            candidate_list.append({'TRACKOR_KEY': candidate['TRACKOR_KEY'], 'C_CANDIDATE_NAME': candidate['C_CANDIDATE_NAME'], 'IKE_Checklists.IKE_UPDATED_AT': candidate['IKE_Checklists.IKE_UPDATED_AT']})

        return candidate_list

    def get_candidates(self, candidate_name_list):
        candidate_names = ''
        for cand in candidate_name_list:
            candidate_names = cand + ',' + candidate_names

        url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/candidate/trackors'
        data = {'fields':'TRACKOR_KEY, C_CANDIDATE_NAME, IKE_Checklists.IKE_UPDATED_AT', 'C_CANDIDATE_NAME':candidate_names[:-1]}
        answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
        if answer.ok:
            return answer.json()
        else:
            raise Exception(answer.text)

    def get_fields_mapping(self):
        self.fm_list_request.read(
                fields=['IFM_FIELD_TRACKOR_TYPE', 'IFM_ESPEED_FIELD_NAME', 'IFM_IKE_FORM_ID', 'IFM_IKE_FIELD_NAME', 'IFM_IKE_FIELD_LABEL', 'IFM_TITLE_NAME']
                )
        if len(self.fm_list_request.errors) > 0:
            raise SystemExit(self.fm_list_request.errors)
        else:
            return self.fm_list_request.jsonData

    def parse_ike_candidates_data(self, ike_candidates_data, fields_mapping):
        form_id = ''
        field_list = []
        for candidate_info in ike_candidates_data:
            ike_collection = candidate_info['ike_collection']
            candidate_info_fields = ike_collection['fields']
            candidate_info_captures = ike_collection['captures']
            candidate_info_updated_at = ike_collection['updatedAt']
            candidate_info_collected_at = ike_collection['collectedAt']
            self.get_data_from_fields(form_id, candidate_info_fields, field_list, fields_mapping, candidate_info_captures)

            if len(field_list) > 0:
                field_list.append({'form_id':form_id, 'trackor_type':'Candidate', 'field_name':'TRACKOR_KEY', 'field_value':candidate_info['TRACKOR_KEY']})
                field_list.append({'form_id':form_id, 'trackor_type':'IKE Checklists', 'field_name':'IKE_UPDATED_AT', 'field_value':candidate_info_updated_at})
                field_list.append({'form_id':form_id, 'trackor_type':'IKE Checklists', 'field_name':'IKE_CAPTURE_DATE', 'field_value':candidate_info_collected_at})

                self.field_list_parsing(field_list)
                file_list = [f for f in os.listdir() if f.endswith('.jpeg')]
                for f in file_list:
                    os.remove(os.path.join(f))
                field_list.clear()
            else:
                self.log('No data / failed to select data for Candidate ' + candidate_info['C_CANDIDATE_NAME'])
   
    def get_data_from_fields(self, form_id, candidate_info_fields, out_field_list, fields_mapping, candidate_info_captures):
        candidate_info_fields.sort(key=lambda val: isinstance(val['value'], list))
        for fields_info in candidate_info_fields:
            field_id = fields_info['field']
            field_name = fields_info['name']
            field_type = fields_info['type']
            field_value = fields_info['value']
            field_provider = None
            if 'provider' in fields_info:
                field_provider = fields_info['provider']
            if isinstance(field_value, list):
                if len(field_value) > 0:
                    for fields_in_field_value in field_value:
                        if 'fields' in fields_in_field_value:
                            form_id = fields_in_field_value['id']
                            fields_in_value = fields_in_field_value['fields']
                            self.get_data_from_fields(form_id, fields_in_value, out_field_list, fields_mapping, candidate_info_captures)
                        else:
                            self.checking_value(field_id, field_name, field_type, fields_in_field_value, field_provider, form_id, fields_mapping, candidate_info_captures, out_field_list)
            else:
                if field_value != '':
                    self.checking_value(field_id, field_name, field_type, field_value, field_provider, form_id, fields_mapping, candidate_info_captures, out_field_list)

    def checking_value(self, field_id, field_name, field_type, field_value, field_provider, form_id, fields_mapping, candidate_info_captures, out_field_list):
        for field_mapping in fields_mapping:
            ike_field_label = field_mapping['IFM_IKE_FIELD_LABEL']
            ike_field_name = field_mapping['IFM_IKE_FIELD_NAME']
            espeed_field_name = field_mapping['IFM_ESPEED_FIELD_NAME']
            title_name = field_mapping['IFM_TITLE_NAME']
            trackor_type = field_mapping['IFM_FIELD_TRACKOR_TYPE']
            if ike_field_label == field_name and field_id == ike_field_name:
                espeed_field_name_in_list = ''
                if len(out_field_list) > 0:
                    for field in out_field_list:
                        field_list_id = field['form_id']
                        field_list_type = field['trackor_type']
                        field_list_name = field['field_name']
                        if field_list_id == form_id and field_list_type == trackor_type and field_list_name == espeed_field_name:
                            espeed_field_name_in_list = espeed_field_name
                            break
                if espeed_field_name_in_list == '':
                    value = None
                    if field_provider is not None and ('IKE_GPS_HEIGHT' in espeed_field_name or 'IKE_GPS_VERT_UNDULATION' in espeed_field_name):
                        value = self.prepare_value_to_add_to_list(field_type, field_provider, espeed_field_name, title_name, candidate_info_captures)
                    elif field_value is not None:
                        value = self.prepare_value_to_add_to_list(field_type, field_value, espeed_field_name, title_name, candidate_info_captures)
                    if value is not None:
                        out_field_list.append({'form_id':form_id, 'trackor_type':trackor_type, 'field_name':espeed_field_name, 'field_value':value})

    def prepare_value_to_add_to_list(self, field_type, field_value, espeed_field_name, title_name, candidate_info_captures):
        if isinstance(field_value, float) or isinstance(field_value, bool):
            field_value = str(field_value)

        if field_type == 'location' and 'longitude' in field_value and '_LONG' in espeed_field_name:
            field_value = str(field_value['longitude'])
        elif field_type == 'location' and 'latitude' in field_value and '_LAT' in espeed_field_name:
            field_value = str(field_value['latitude'])
        elif field_type == 'location' and 'altitude' in field_value and 'ALTITUDE' in espeed_field_name:
            field_value = str(field_value['altitude'])
        elif field_type == 'location' and 'accuracy' in field_value and 'ACCURACY' in espeed_field_name:
            field_value = str(field_value['accuracy'])
        elif 'antennaHeight' in field_value and 'IKE_GPS_HEIGHT' in espeed_field_name:
            field_value = str(field_value['antennaHeight'])
        elif 'undulation' in field_value and 'IKE_GPS_VERT_UNDULATION' in espeed_field_name:
            field_value = str(field_value['undulation'])
        elif field_type == 'nestedlist':
            if title_name == None:
                field_value = field_value['value']
            else:
                if isinstance(field_value, list):
                    for title in field_value:
                        if title_name in title['title']:
                            field_value = title['value']
                            break
                else:
                    if title_name in field_value['title']:
                        field_value = field_value['value']
                if isinstance(field_value, dict):
                    field_value = None
        elif field_type == 'selectlist' and 'title' in field_value:
            if field_value['value'] == 'unselected':
                field_value = None
            else:
                field_value = field_value['title']
        elif field_type == 'vector' and 'distance' in field_value:
            field_value = str(float(field_value['distance']) / .3048)
        elif field_type == 'image':
            field_value = self.get_ike_image(field_value, candidate_info_captures)
        elif field_type == 'truesizecapture' in field_type:
            field_value = self.get_ike_image(field_value, candidate_info_captures)
        elif field_type == 'height' and field_value is not None:
            field_value = str(float(field_value) / .3048)
        else: field_value = field_value.title()

        return field_value

    def get_ike_image(self, field_value, captures):
        for collect in captures:
            if re.search(field_value, collect['id']) is not None:
                if collect['type'] == 'image':
                    field_value = collect['imageUrl']
                elif collect['type'] == 'truesize':
                    field_value = collect['compositeUrl']
                if re.search('meters', field_value) is not None:
                    field_value = field_value.replace('meters', 'feet')
                break

        if 'https' in field_value:
            image_name = re.split('/',field_value)
            image_name = image_name[len(image_name)-1]

            image = requests.get(field_value, headers={'Accept':'application/json'})
            img_file = open(image_name, 'wb')
            img_file.write(image.content)
            img_file.close

            return image_name
        else:
            return None

    def field_list_parsing(self, field_list):
        candidate_id = 0
        candidate_name = None
        data_checklists = []
        for field_data in field_list:
            if field_data['trackor_type'] == 'Candidate':
                try:
                    data_checklists = self.get_checklist(field_data['field_value'])
                except Exception as e:
                    self.log('Failed to get_checklist. Exception [%s]' % str(e))

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
            field_name = field_data['field_name']
            field_value = field_data['field_value']
            trackor_type = field_data['trackor_type']
            form_id = field_data['form_id']
            if trackor_type == 'IKE Checklists':
                if '.jpeg' in field_value:
                    image_list.append({'trackor_type':field_name, 'file_name':field_value})
                else:
                    checklists_dict[field_name] = field_data['field_value']
                continue
            if trackor_type == 'Candidate':
                candidate_dict[field_name] = field_data['field_value']
                continue
            if trackor_type == 'IKE Pole Placement':
                if len(placement_list) > 0:
                    for pl in placement_list:
                        if form_id == pl['form_id']:
                            pl.update({'form_id':form_id, field_name:field_value})
                            placement_id = form_id
                            break
                    if placement_id != form_id:
                        placement_list.append({'form_id':form_id, field_name:field_value})
                        placement_id = form_id
                else:
                    placement_list.append({'form_id':form_id, field_name:field_value})
                    placement_id = form_id
                continue
            if trackor_type == 'IKE Anchors':
                if len(anchors_list) > 0:
                    for al in anchors_list:
                        if form_id == al['form_id']:
                            al.update({'form_id':form_id, field_name:field_value})
                            anchors_id = form_id
                            break
                    if anchors_id != form_id:
                        anchors_list.append({'form_id':form_id, field_name:field_value})
                else:
                    anchors_list.append({'form_id':form_id, field_name:field_value})
                    anchors_id = form_id
                continue
            if trackor_type == 'IKE Spans':
                if len(spans_list) > 0:
                    for sl in spans_list:
                        if form_id == sl['form_id']:
                            sl.update({'form_id':form_id, field_name:field_value})
                            span_id = form_id
                            break
                    if span_id != form_id:
                        spans_list.append({'form_id':form_id, field_name:field_value})
                else:
                    spans_list.append({'form_id':form_id, field_name:field_value})
                    span_id = form_id
                continue
            if trackor_type == 'IKE Equipment':
                if len(equipment_list) > 0:
                    for el in equipment_list:
                        if form_id == el['form_id']:
                            el.update({'form_id':form_id, field_name:field_value})
                            equipment_id = form_id
                            break
                    if equipment_id != form_id:
                        equipment_list.append({'form_id':form_id, field_name:field_value})
                else:
                    equipment_list.append({'form_id':form_id, field_name:field_value})
                    equipment_id = form_id

        if len(checklists_dict) > 0 and len(candidate_dict) > 0 and candidate_id == 0 and candidate_name == None:
            try:
                answer = self.create_trackors('IKE_Checklists', checklists_dict, 'Candidate', candidate_dict)
            except Exception as e:
                self.log('Failed to create IKE Checklist for Candidate ' + str(candidate_dict['TRACKOR_KEY']) + '. Exception [%s]' % str(e))
                answer = None

            if answer is not None:
                candidate_id = answer['TRACKOR_ID']
                candidate_name = answer['TRACKOR_KEY']
                checklists_dict.clear()

        if candidate_id != 0:
            if len(checklists_dict) > 0:
                try:
                    self.update_checklist_data(candidate_id, checklists_dict)
                except Exception as e:
                    self.log('Failed to update IKE Checklist for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))

            if len(image_list) > 0:
                for image_file in image_list:
                    try:
                        self.attach_image_file(candidate_id, image_file)
                    except Exception as e:
                        self.log('Failed to attach image file for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))

        if candidate_name is not None:                    
            if len(placement_list) > 0:
                pl_image_file_list = []
                for pl in placement_list:
                    pl.pop('form_id', None)
                    for item in list(pl.items()):
                        if 'jpeg' in item[1]:
                            pl_image_file_list.append({'trackor_type':item[0], 'file_name':item[1]})
                            pl.pop(item[0], None)
                    try:
                        answer = self.create_trackors('IKE_POLE_PLACEMENT', pl, 'IKE_Checklists', {'TRACKOR_KEY':candidate_name})
                    except Exception as e:
                        self.log('Failed to create IKE Pole Placement for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))
                        answer = None

                    if answer is not None and len(pl_image_file_list) > 0:
                        for pl_image_file in pl_image_file_list:
                            try:
                                self.attach_image_file(answer['TRACKOR_ID'], pl_image_file)
                            except Exception as e:
                                self.log('Failed to attach image file IKE Pole Placement for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))

                    pl_image_file_list.clear()

            if len(anchors_list) > 0:
                al_image_file_list = []
                for al in anchors_list:
                    al.pop('form_id', None)
                    for item in list(al.items()):
                        if 'jpeg' in item[1]:
                            al_image_file_list.append({'trackor_type':item[0], 'file_name':item[1]})
                            al.pop(item[0], None)
                    try:
                        answer = self.create_trackors('IKE_ANCHORS', al, 'IKE_Checklists', {'TRACKOR_KEY':candidate_name})
                    except Exception as e:
                        self.log('Failed to create IKE Anchors for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))
                        answer = None
                    
                    if answer is not None and len(al_image_file_list) > 0:
                        for al_image_file in al_image_file_list:
                            try:
                                self.attach_image_file(answer['TRACKOR_ID'], al_image_file)
                            except Exception as e:
                                self.log('Failed to attach image file IKE Anchors for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))

                    al_image_file_list.clear()

            if len(spans_list) > 0:
                sl_image_file_list = []
                for sl in spans_list:
                    sl.pop('form_id', None)
                    for item in list(sl.items()):
                        if 'jpeg' in item[1]:
                            sl_image_file_list.append({'trackor_type':item[0], 'file_name':item[1]})
                            sl.pop(item[0], None)
                    try:
                        answer = self.create_trackors('IKE_Span', sl, 'IKE_Checklists', {'TRACKOR_KEY':candidate_name})
                    except Exception as e:
                        self.log('Failed to create IKE Span for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))
                        answer = None
                    
                    if answer is not None and len(sl_image_file_list) > 0:
                        for sl_image_file in sl_image_file_list:
                            try:
                                self.attach_image_file(answer['TRACKOR_ID'], sl_image_file)
                            except Exception as e:
                                self.log('Failed to attach image file IKE Span for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))

                    sl_image_file_list.clear()

            if len(equipment_list) > 0:
                el_image_file_list = []
                for el in equipment_list:
                    el.pop('form_id', None)
                    for item in list(el.items()):
                        if 'jpeg' in item[1]:
                            el_image_file_list.append({'trackor_type':item[0], 'file_name':item[1]})
                            el.pop(item[0], None)
                    try:
                        answer = self.create_trackors('IKE_EQUIPMENT', el, 'IKE_Checklists', {'TRACKOR_KEY':candidate_name})
                    except Exception as e:
                        self.log('Failed to create IKE Equipment for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))
                        answer = None
                    
                    if answer is not None and len(el_image_file_list) > 0:
                        for el_image_file in el_image_file_list:
                            try:
                                self.attach_image_file(answer['TRACKOR_ID'], el_image_file)
                            except Exception as e:
                                self.log('Failed to attach image file IKE Equipment for Candidate ' + str(candidate_name) + '. Exception [%s]' % str(e))

                    el_image_file_list.clear()

    def update_checklist_data(self, candidate_id, checklists_dict):
        url = 'https://' + self.url_onevizion + '/api/v3/trackors/' + str(candidate_id)
        data = checklists_dict
        answer = requests.put(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
        if answer.ok:
            return answer
        else:
            raise Exception(answer.text)

    def attach_image_file(self, trackor_id, image_file):
        url = 'https://' + self.url_onevizion + '/api/v3/trackor/' + str(trackor_id) + '/file/' + image_file['trackor_type']
        data = {'file_name':image_file['file_name']}
        files = {'file':(image_file['file_name'], open(image_file['file_name'], 'rb'))}
        answer = requests.post(url, files=files, params=data, headers={'Accept':'application/json'}, auth=self.auth_onevizion)
        if answer.ok:
            return answer
        else:
            raise Exception(answer.text)

    def get_checklist(self, candidate_id):
        url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/IKE_Checklists/trackors'
        data = {'Candidate.TRACKOR_KEY':candidate_id}
        answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
        if answer.ok:
            return answer.json()
        else:
            raise Exception(answer.text)

    def create_trackors(self, chield_trackor, chield_dict, parent_trackor, parent_dict):
        url = 'https://' + self.url_onevizion + '/api/v3/trackor_types/' + chield_trackor + '/trackors'
        data = {'fields':chield_dict, 'parents':[{'trackor_type':parent_trackor, 'filter':parent_dict}]}
        answer = requests.post(url, data=json.dumps(data), headers=self.headers, auth=self.auth_onevizion)
        if answer.ok:
            return answer.json()
        else:
            raise Exception(answer.text)

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
