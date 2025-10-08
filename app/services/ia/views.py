from flask import Blueprint, jsonify

ia_bp = Blueprint("ia", __name__)

@ia_bp.route("/", methods=["GET"])
def ia():
    return jsonify({"message": "IA"})