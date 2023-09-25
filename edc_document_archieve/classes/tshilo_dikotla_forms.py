from django.apps import apps as django_apps


class TshiloDikotlaForms:

    @property
    def non_crfs(self):
        models = []
        excluded_apps = [
            'Assent',
            'Adult Main Consent',
            'Continued Participation',
            'Parental Consent For Child',
            'Birth Certificate'
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
    def maternal_crfs(self):
        models = [
        ]
        return models

    @property
    def maternal_forms(self):
        data = {
            'crfs': self.maternal_crfs,
            'non_crfs': self.non_crfs
        }
        return data

    @property
    def infant_forms(self):
        data = {
            'crfs': [],
            'non_crfs': self.non_crfs
        }
        return data
