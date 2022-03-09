import datetime
import os
import pytz
import PIL

from rest_framework.response import Response
from rest_framework.views import APIView
from .flourish_home_view_mixin import FlourishHomeViewMixin
from django.db.utils import IntegrityError
from django.apps import apps as django_apps
from edc_appointment.constants import NEW_APPT
from django.db.models import ManyToOneRel
from dateutil.parser import parse
from django.utils.timezone import make_aware

from PIL import Image


class HomeView(FlourishHomeViewMixin, APIView):

    @property
    def consent_image_model_cls(self):
        consent_image_model = 'edc_odk.consentimage'
        return django_apps.get_model(consent_image_model)

    @property
    def specimen_consent_image_model_cls(self):
        specimen_consent_image_model = 'edc_odk.specimenconsentimage'
        return django_apps.get_model(specimen_consent_image_model)

    @property
    def national_id_image_model_cls(self):
        nation_id_image_model = 'edc_odk.nationalidentityimage'
        return django_apps.get_model(nation_id_image_model)

    @property
    def note_to_file_image_model_cls(self):
        note_to_file_image_model = 'edc_odk.notetofiledocs'
        return django_apps.get_model(note_to_file_image_model)

    @property
    def clinician_notes_archive_image_model_cls(self):
        clinician_notes_archive_image_model = 'edc_odk.cliniciannotesimagearchive'
        return django_apps.get_model(clinician_notes_archive_image_model)

    @property
    def lab_results_file_model_cls(self):
        labresults_file_model = 'edc_odk.labresultsfile'
        return django_apps.get_model(labresults_file_model)

    def clinician_notes_image_model(self, app_name=None):
        return '%s.cliniciannotesimage' % app_name

    def clinician_notes_model_cls(self, app_name=None):
        app_config = django_apps.get_app_config(
            'edc_odk').clinician_notes_models

        clinician_notes_model = app_config.get(app_name, 'default')

        if clinician_notes_model:
            return django_apps.get_model(
                '%s.%s' % (app_name, clinician_notes_model))

    def get(self, request):
        studies = {
            'flourish': {
                'pids': self.pids,
                'caregiver_forms': self.caregiver_forms,
                'child_forms': self.child_forms
            },
            'tshilo-dikotla': {},
        }

        results = [
            {
                'subject_identifier': 'B142-040990462-9',
                'visit_code': '1000M',
                'timepoint': 0
            }
        ]
        print(self.populate_model_objects(
            'flourish_caregiver',
            results,
            self.clinician_notes_model_cls('flourish_caregiver'),
        ))
        return Response(studies)

    def post(self, request):
        tz = pytz.timezone('Africa/Gaborone')
        # All data capture before the date below
        created = datetime.datetime(2022, 3, 11, 0, 12)
        created = make_aware(created, tz, True)
        results = [
            {
                'subject_identifier': 'B142-040990462-9',
                'visit_code': '1000M',
                'timepoint': 0,
                'image_name': [request.data['image_name']],
                'image_url': [request.data['image_url']],
                'date_captured': created,
                'username': 'moffatmore',
                'model_cls': 'flourish_caregiver',
                'model_name': ''
            }
        ]
        img_cls = django_apps.get_model(self.clinician_notes_image_model('flourish_caregiver'))
        image_cls_field = 'clinician_notes'
        self.populate_model_objects(
            'flourish_caregiver',
            results,
            self.clinician_notes_model_cls('flourish_caregiver'),
            img_cls,
            image_cls_field)

        return Response("Hello")

    def populate_model_objects(self, app_name, result, model_cls, img_cls, image_cls_field):
        updated = 0
        count = 0
        for data_dict in result:
            if data_dict['visit_code']:
                # Get visit
                visit_obj = self.get_app_visit_model_obj(
                    app_name,
                    data_dict['subject_identifier'],
                    data_dict['visit_code'],
                    data_dict['timepoint'])
                visit_models = self.get_visit_models().get(app_name)
                field_name = None
                if visit_models:
                    field_name = visit_models[0]
                if visit_obj:
                    print({f'{field_name}': visit_obj})
                    try:
                        obj, created = model_cls.objects.get_or_create(
                            report_datetime__lte=visit_obj.report_datetime,
                            **{f'{field_name}': visit_obj}, )
                        if created:
                            self.create_image_obj_upload_image(
                                img_cls,
                                image_cls_field,
                                obj,
                                data_dict)
                            count += 1
                        else:
                            imgs_updated = self.update_existing_image_objs(
                                img_cls,
                                image_cls_field,
                                obj,
                                data_dict)
                            if imgs_updated:
                                updated += 1
                    except IntegrityError as e:
                        raise Exception(e)
        return count, updated

    def get_app_visit_model_obj(
            self, app_name, subject_identifier, visit_code, timepoint):
        visit_model_obj = None
        visit_models = self.get_visit_models().get(app_name)

        if visit_models:
            visit_model_cls = django_apps.get_model(
                visit_models[1])

            visit_model_obj = visit_model_cls.objects.filter(
                subject_identifier=subject_identifier,
                visit_code=visit_code,
                visit_code_sequence=timepoint).exclude(
                appointment__appt_status=NEW_APPT).order_by('-report_datetime').last()
            if not visit_model_obj:
                message = (f'Failed to get visit for {subject_identifier}, at '
                           f'visit {visit_code}. Visit does not exist.')

        return visit_model_obj

    def get_visit_models(self):
        app_config = django_apps.get_app_config('edc_visit_tracking')
        return app_config.visit_models

    def update_existing_image_objs(self, images_cls, field_name, obj, fields):
        existing_datetime = self.recent_image_obj_datetime(
            images_cls, field_name, obj, fields)
        if existing_datetime:
            print(existing_datetime)
            if fields.get('date_captured') > existing_datetime:
                self.create_image_obj_upload_image(images_cls, field_name, obj, fields)
                print(fields.get('date_captured'))
            return True
        else:
            return False

    def recent_image_obj_datetime(self, images_cls, field_name, obj, fields):
        recent_captured = list()
        related_images = [field.get_accessor_name() for field in
                          obj._meta.get_fields() if issubclass(type(field), ManyToOneRel)]

        for related_image in related_images:
            recent_obj = getattr(
                obj, related_image).order_by('-datetime_captured').first()
            if recent_obj:
                recent_captured.append(recent_obj.datetime_captured)
            else:
                self.create_image_obj_upload_image(
                    images_cls, field_name, obj, fields)

        return max(recent_captured) if recent_captured else False

    def create_image_obj_upload_image(
            self, images_cls, field_name, obj, fields):
        image_names = [field for field in fields.keys() if 'image_name' in field]
        image_urls = [field for field in fields.keys() if 'image_url' in field]

        result = zip(image_names, image_urls)
        image_cls = None

        for image_name, image_url in result:
            if isinstance(images_cls, dict):
                image_cls = images_cls.get(
                    image_name.replace('_image_name', ''))
            else:
                image_cls = images_cls

            i = 0
            while i < len(fields.get(image_name)):

                upload_to = image_cls.image.field.upload_to

                # Check if path is func or string
                upload_to = upload_to(None, None) if callable(upload_to) else upload_to

                upload_success = self.image_file_upload(
                    fields.get(image_url)[i],
                    fields.get(image_name)[i],
                    upload_to)

                if upload_success:
                    datetime_captured = fields.get('date_captured')
                    local_timezone = pytz.timezone('Africa/Gaborone')
                    datetime_captured.astimezone(local_timezone)
                    # create image model object
                    image_cls.objects.create(
                        **{f'{field_name}': obj},
                        image=upload_to + fields.get(image_name)[i],
                        user_uploaded=fields.get('username'),
                        datetime_captured=datetime_captured)

                    # Add a stamp to the image upload
                    path = 'media/%(upload_dir)s%(filename)s' % {
                        'filename': fields.get(image_name)[i],
                        'upload_dir': upload_to}
                    #self.add_image_stamp(image_path=path)
                    i += 1

    def add_image_stamp(self, image_path=None, position=(25, 25), resize=(600, 600)):
        """
        Superimpose image of a stamp over copy of the base image
        @param image_path: dir to base image
        @param position: pixels(w,h) to superimpose stamp at
        """
        base_image = Image.open(image_path)
        stamp = Image.open('media/stamp/true-copy.png')
        import pdb;
        pdb.set_trace()
        if resize:
            stamp = stamp.resize(resize, PIL.Image.ANTIALIAS)

        width, height = base_image.size
        stamp_width, stamp_height = stamp.size

        # Determine orientation of the base image before pasting stamp
        if width < height:
            pos_width = round(width / 2) - round(stamp_width / 2)
            pos_height = height - stamp_height
            position = (pos_width, pos_height)
        elif width > height:
            stamp = stamp.rotate(90)
            pos_width = width - stamp_width
            pos_height = round(height / 2) - round(stamp_height / 2)
            position = (pos_width, pos_height)

        # paste stamp over image
        base_image.paste(stamp, position, mask=stamp)
        base_image.save(image_path)

    def image_file_upload(self, file, filename, upload_to):
        image_path = 'media/%(upload_dir)s' % {'upload_dir': upload_to}
        if not os.path.exists(image_path):
            os.makedirs(image_path)
        with open('%(path)s%(filename)s' % {'path': image_path, 'filename': filename}, 'wb') as f:
            f.write(file.read())
        return True

