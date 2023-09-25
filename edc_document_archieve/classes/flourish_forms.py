from django.apps import apps as django_apps


class FlourishForms:
    odk_app = 'edc_odk'

    @property
    def caregiver_non_crfs(self):
        models = []
        excluded_apps = [
            'Assent',
            'Continued Participation',
            'Consent Copies',
            'Birth Certificate',
            'Specimen Consent Copies',
            'Clinician Notes Archives',
        ]
        app_models = django_apps.get_app_config(self.odk_app).get_models()
        for model in app_models:
            if (model._meta.verbose_name.istitle() and model._meta.verbose_name
                    not in excluded_apps):
                models.append({
                    'app_label': model._meta.app_label,
                    'model_name': model._meta.verbose_name
                })
            if model._meta.verbose_name == 'Note to file':
                models.append({
                    'app_label': model._meta.app_label,
                    'model_name': model._meta.verbose_name
                })
        return models

    @property
    def caregiver_crfs(self):
        models = [
            {
                'app_label': 'flourish_caregiver',
                'model_name': 'Clinician Notes',
            },
        ]
        return models

    @property
    def caregiver_forms(self):
        data = {
            'crfs': self.caregiver_crfs,
            'non_crfs': self.caregiver_non_crfs
        }
        return data

    @property
    def child_forms(self):
        data = {
            'crfs': [{
                'app_label': 'flourish_child',
                'model_name': 'Child Clinician Notes'
            }],
            'non_crfs': [{
                'model_name': 'Assent',
                'app_label': 'edc_odk',
            },
                {
                    'model_name': 'Continued Participation',
                    'app_label': 'edc_odk',
                },
                {
                    'model_name': 'Omang Copies',
                    'app_label': 'edc_odk',
                },
                {
                    'model_name': 'Birth Certificate',
                    'app_label': 'edc_odk',
                },
                {
                    'model_name': 'Note to file',
                    'app_label': 'edc_odk',
                },
                {
                    'model_name': 'Lab Results Files',
                    'app_label': 'edc_odk',
                },
            ]
        }
        return data
