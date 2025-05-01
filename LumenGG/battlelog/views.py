from django.shortcuts import render

# Create your views here.
def sim(req):
    return render(req, 'battlelog/sim.html', {})

def stream(req):
    return render(req, 'battlelog/stream.html', {})