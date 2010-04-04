from django.conf.urls.defaults import *
import reporter.views

urlpatterns = patterns('',
    #url(r'new', ContactWizard([ContactForm1, ContactForm2]), name='new'),
    url(r'new', reporter.views.new, name='new'),
)
