from datetime import date

from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, TestCase
from mock import patch

from foia_hub.models import Agency, FOIARequest, Office, Requester
from foia_hub.models import ReadingRoomUrls
from foia_hub.views import get_agency_list


class RequestFormTests(SimpleTestCase):
    def setUp(self):
        self.emails = ["foia1@example.com", "foia2@example.com"]

        self.agency = Agency(
            name='Agency With Offices', zip_code=20404, emails=self.emails)
        self.agency.save()

        self.office = Office(
            agency=self.agency, name='Office 1', zip_code=20404,
            emails=self.emails)
        self.office.save()

        self.office2 = Office(
            agency=self.agency, name='Office 2', zip_code=20404,
            emails=self.emails)
        self.office2.save()

        self.agency2 = Agency(
            name='Agency Without Offices', zip_code=20009, emails=self.emails)
        self.agency2.save()

        self.requester = Requester.objects.create(
            first_name='Alice', last_name='Bobson', email='eve@example.com')
        self.request = FOIARequest.objects.create(
            requester=self.requester, office=self.office,
            date_end=date.today(), request_body='All the cheese')

    # destroy them all
    def tearDown(self):
        for model in [FOIARequest, Requester, Office, Agency]:
            model.objects.all().delete()

    def test_request_form_successful(self):
        """The agency name should be present in the request form"""
        response = self.client.get(reverse(
            'form', kwargs={'slug': self.agency.slug}))
        self.assertContains(response, self.agency.name)

    def test_request_form_404(self):
        """Should get a 404 if requesting an agency that doesn't exist"""
        response = self.client.get(reverse(
            'form', kwargs={'slug': 'does-not-exist'}))
        self.assertEqual(404, response.status_code)

    def test_request_success(self):
        """Request should be retrieved and displayed"""
        response = self.client.get(reverse(
            'success', kwargs={'id': self.request.id}))
        self.assertContains(response, self.requester.email)
        self.assertContains(response, self.agency.name)

    def test_request_success_404(self):
        """Should get a 404 if trying to get a success page for a request
        which doesn't exist"""
        response = self.client.get(reverse(
            'success', kwargs={'id': 9999999999}))
        self.assertEqual(404, response.status_code)

    def test_contact_landing_404(self):
        """Verify that non-existing agency/offices cause 404s"""
        response = self.client.get(reverse(
            'contact_landing', kwargs={'slug': 'sssss'}))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(
            reverse('contact_landing', kwargs={'slug': 'sss--ss'}))
        self.assertEqual(response.status_code, 404)

    def test_contact_landing_success(self):
        """If loading an agency or a top-level office, we should see agency
        name. If an office, we should not see peer offices."""

        list_fingerprint = "Make your FOIA request directly"
        list_fingerprint += " to the most relevant group or component"

        response = self.client.get(reverse(
            'contact_landing', kwargs={'slug': self.agency.slug}))
        self.assertContains(response, self.agency.name)
        self.assertContains(response, self.office.name)
        self.assertContains(response, self.office2.name)
        self.assertContains(response, list_fingerprint)

        response = self.client.get(reverse(
            'contact_landing', kwargs={'slug': self.office.slug}))
        self.assertContains(response, self.agency.name)
        self.assertContains(response, self.office.name)
        self.assertNotContains(response, self.office2.name)
        self.assertNotContains(response, list_fingerprint)

        response = self.client.get(reverse(
            'contact_landing', kwargs={'slug': self.agency2.slug}))
        self.assertContains(response, self.agency2.name)
        self.assertNotContains(response, self.office.name)
        self.assertNotContains(response, self.office2.name)
        self.assertNotContains(response, list_fingerprint)

    def test_learn(self):
        """The /learn/ page should load without errors."""
        response = self.client.get(reverse('learn'))
        self.assertEqual(response.status_code, 200)

    def test_about(self):
        """The /about/ page should load without errors."""
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)


class MainPageTests(TestCase):
    fixtures = ['agencies_test.json']

    def test_main_page(self):
        """ The main page should load without errors. """
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertTrue('What is FOIA?' in content)

    @patch.dict('foia_hub.views.env.globals',
                {'ANALYTICS_ID': 'MyAwesomeAnalyticsCode'})
    def test_analytics_id(self):
        """Verify that the analytics id appears *somewhere* on the page"""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'MyAwesomeAnalyticsCode')

    def test_get_agency_list(self):
        agencies = get_agency_list()
        self.assertEqual(
            agencies, [
                {
                    'name': 'Department of Commerce',
                    'slug': 'department-of-commerce'},
                {
                    'name': 'Department of Homeland Security',
                    'slug': 'department-of-homeland-security'
                },
                {
                    'name': 'U.S. Patent and Trademark Office',
                    'slug': 'us-patent-and-trademark-office'
                }])


class AgenciesPageTests(TestCase):

    fixtures = ['agencies_test.json']

    def test_agencies_page(self):
        """ The /agencies/ page should load without errors. """
        response = self.client.get(reverse('agencies'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertTrue('Department of Homeland Security' in content)

    def test_agencies_search_list(self):
        """ The /agencies/ page should filter agencies by a search term. """
        query = "department"
        response = self.client.get(reverse('agencies') + "?query=" + query)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertTrue('Department of Homeland Security' in content)
        self.assertTrue('Department of Commerce' in content)
        self.assertTrue('Patent and Trademark Office' not in content)

    def test_agencies_search_one(self):
        """ The /agencies/ page should redirect to an agency if there's only
        one result. """

        query = "dhs"
        dhs = Agency.objects.filter(abbreviation='DHS')[0]
        response = self.client.get(reverse('agencies') + "?query=" + query)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            "http://testserver" + reverse(
                'contact_landing', kwargs={'slug': dhs.slug}),
            response['Location']
        )

    def test_agencies_search_none(self):
        """ The /agencies/ page should display a message if there are no
        results. """

        query = "kjlasdhfjhsdfljsdhflkasdjh"
        response = self.client.get(reverse('agencies') + "?query=" + query)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertTrue('Department of Homeland Security' not in content)
        self.assertTrue('Department of Commerce' not in content)
        self.assertTrue('Patent and Trademark Office' not in content)
        self.assertTrue('no agencies matching your search' in content)


class ContactPageTests(TestCase):
    fixtures = ['agencies_test.json', 'offices_test.json']

    def test_inaccurate_contact(self):
        response = self.client.get(
            reverse(
                'contact_landing',
                args=['department-of-commerce--census-bureau']))
        self.assertTrue(200, response.status_code)
        content = response.content.decode('utf-8')
        self.assertTrue('18f-foia@gsa.gov' in content)

    def test_no_email(self):
        """ For agencies without their own request form, and without an email
        address, do not display a FOIA request form. """

        a = Agency(name="Broadcasting Board of Governors", slug="brodcasting")
        a.save()

        response = self.client.get(
            reverse('contact_landing', args=['broadcasting']))
        self.assertTrue(200, response.status_code)
        content = response.content.decode('utf-8')
        self.assertTrue('Request online' not in content)

    def test_reading_rooms(self):
        rone = ReadingRoomUrls(link_text='Url One', url='http://urlone.gov')
        rone.save()
        rtwo = ReadingRoomUrls(link_text='Url Two', url='http://urltwo.gov')
        rtwo.save()

        census = Office.objects.get(
            slug='department-of-commerce--census-bureau')
        census.reading_room_urls.add(rone, rtwo)

        response = self.client.get(
            reverse(
                'contact_landing',
                args=['department-of-commerce--census-bureau']))
        self.assertTrue(200, response.status_code)
        content = response.content.decode('utf-8')
        self.assertTrue('FOIA Libraries' in content)
        self.assertTrue('Url One' in content)
        self.assertTrue('Url Two' in content)
