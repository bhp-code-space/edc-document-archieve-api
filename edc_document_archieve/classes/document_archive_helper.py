import os

import PIL
import pytz
from PIL import Image
from django.db.utils import IntegrityError
from django.apps import apps as django_apps
from edc_appointment.constants import NEW_APPT
from django.db.models import ManyToOneRel
from .document_archive_mixin import DocumentArchiveMixin
from django.utils.timezone import make_aware
from dateutil.parser import parse


class DocumentArchiveHelper(DocumentArchiveMixin):
    def populate_model_objects(self, data_dict, files):
        updated = 0
        count = 0
        model_name = data_dict['model_name'].replace('_', '')
        app_name = data_dict['app_label']
        img_cls = self.get_image_cls(model_name, app_name)
        image_cls_field = data_dict['model_name']
        model_cls = django_apps.get_model('%s.%s' % (app_name, model_name))

        if data_dict.get('visit_code'):
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
                try:
                    obj, created = model_cls.objects.get_or_create(
                        report_datetime__gte=visit_obj.report_datetime,
                        **{f'{field_name}': visit_obj}, )
                    if created:
                        self.create_image_obj_upload_image(
                            img_cls,
                            image_cls_field,
                            obj,
                            data_dict,
                            files)
                        count += 1
                    else:
                        imgs_updated = self.update_existing_image_objs(
                            img_cls,
                            image_cls_field,
                            obj,
                            data_dict,
                            files)
                        if imgs_updated:
                            updated += 1
                except IntegrityError as e:
                    raise Exception(e)

        elif data_dict.get('subject_identifier'):
            try:
                if data_dict.get('consent_version'):
                    obj, created = model_cls.objects.get_or_create(
                        subject_identifier=data_dict.get('subject_identifier'),
                        version=data_dict.get('consent_version'))
                else:
                    obj, created = model_cls.objects.get_or_create(
                        subject_identifier=data_dict.get('subject_identifier'))
                if created:
                    self.create_image_obj_upload_image(
                        img_cls,
                        image_cls_field,
                        obj,
                        data_dict,
                        files)
                    count += 1
                else:
                    imgs_updated = self.update_existing_image_objs(
                        img_cls,
                        image_cls_field,
                        obj,
                        data_dict,
                        files)
                    if imgs_updated:
                        updated += 1

            except IntegrityError as e:
                raise Exception(e)
        else:
            obj, created = model_cls.objects.get_or_create(
                identifier=data_dict.get('identifier'))
            if created:
                self.create_image_obj_upload_image(
                    img_cls,
                    image_cls_field,
                    obj,
                    data_dict,
                    files)
        return count, updated

    def get_app_visit_model_obj(
            self, app_name, subject_identifier, visit_code, timepoint
    ):
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

    def update_existing_image_objs(self, images_cls, field_name, obj, fields, files):
        existing_datetime = self.recent_image_obj_datetime(
            images_cls, field_name, obj, fields, files)
        data_captured = parse(fields.get('date_captured'))
        tz = pytz.timezone('Africa/Gaborone')
        data_captured = make_aware(data_captured, tz, True)
        if existing_datetime:
            if data_captured > existing_datetime:
                self.create_image_obj_upload_image(images_cls, field_name, obj, fields, files)
                print(fields.get('date_captured'))
            return True
        else:
            return False

    def recent_image_obj_datetime(self, images_cls, field_name, obj, fields, files):
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
                    images_cls, field_name, obj, fields, files)

        return max(recent_captured) if recent_captured else False

    def create_image_obj_upload_image(
            self, images_cls, field_name, obj, fields, files):
        print(len(files))
        for file in files:
            upload_to = images_cls.image.field.upload_to
            # Check if path is func or string
            upload_to = upload_to(None, None) if callable(upload_to) else upload_to
            upload_success = self.image_file_upload(file, file.name, upload_to)

            if upload_success:
                datetime_captured = fields.get('date_captured')
                datetime_captured = parse(datetime_captured)
                local_timezone = pytz.timezone('Africa/Gaborone')
                datetime_captured.astimezone(local_timezone)
                # create image model object
                images_cls.objects.create(
                    **{f'{field_name}': obj},
                    image=upload_to + file.name,
                    user_uploaded=fields.get('username'),
                    datetime_captured=datetime_captured)
        return None
        

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

    def get_image_cls(self, model_name, app_name):
        if model_name == 'consentcopies':
            return self.consent_image_model_cls
        elif model_name == 'omangcopies':
            return self.national_id_image_model_cls
        elif model_name == 'specimenconsentcopies':
            return self.specimen_consent_image_model_cls
        elif model_name == 'cliniciannotesarchives':
            return self.specimen_consent_image_model_cls
        elif model_name == 'labresultsfile':
            return self.specimen_consent_image_model_cls
        elif model_name == 'cliniciannotes':
            return self.clinician_notes_image_model(app_name)
