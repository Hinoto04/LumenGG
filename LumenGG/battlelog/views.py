from django.shortcuts import render

# Create your views here.
def sim(req):
    return render(req, 'battlelog/sim.html', {})