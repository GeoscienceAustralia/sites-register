from flask import Blueprint, render_template, Response

routes = Blueprint('controller', __name__)


@routes.route('/')
def index():
    return render_template(
        'page_index.html'
    )


@routes.route('/func')
def func():
    return Response('this is a response from a function', mimetype='text/plain')

