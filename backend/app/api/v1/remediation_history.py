from fastapi import APIRouter

from app.services.remediation_audit_history import (
    get_remediation_history,
)


router = APIRouter(
    prefix="/executive-remediation",
    tags=["executive-remediation"],
)



@router.get(
    "/history"
)
def history():

    return {

        "engine":
        {
            "name":
            "SS4TS Executive Remediation History",

            "version":
            "1.0.0"
        },


        "count":
        len(
            get_remediation_history()
        ),


        "timeline":
        get_remediation_history()

    }
