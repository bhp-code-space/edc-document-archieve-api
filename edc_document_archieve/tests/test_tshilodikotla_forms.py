import unittest
from unittest.mock import patch

from django.apps import AppConfig, apps

from edc_document_archieve.classes.tshilo_dikotla_forms import TshiloDikotlaForms


class TestTshiloDikotlaForms(unittest.TestCase):
    def setUp(self):
        self.form = TshiloDikotlaForms()
        self.form.odk_app = 'edc_document_archieve'
        # app nam

    def test_maternal_crfs(self):
        crfs = self.form.maternal_crfs
        self.assertListEqual(crfs, [])

    def test_maternal_forms(self):
        data = self.form.maternal_forms
        self.assertIn('crfs', data)
        self.assertIn('non_crfs', data)

    def test_infant_forms(self):
        data = self.form.infant_forms
        self.assertIn('crfs', data)
        self.assertIn('non_crfs', data)


if __name__ == '__main__':
    unittest.main()
