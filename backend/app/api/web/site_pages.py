"""公开网站(spec 2026-10-22-website-v1)。

⚠️ 同 share_pages:只读 repo 层,不带身份、不调内容接口、不点火。
⚠️ 音频只有试听件、只经 /w/audio 签发短时效地址。
"""

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.web.share_pages import _not_found
from app.core.database import get_db
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.storage import get_object_storage
from app.services.website.trials import trial_parts, trial_qids

router = APIRouter(tags=["website"])


@router.get("/w/audio/{museum_slug}/{qid}/{part}")
def trial_audio(
    museum_slug: str, qid: str, part: str, lang: str = "", db: Session = Depends(get_db)
):
    m = (
        db.query(Museum)
        .filter(Museum.slug == museum_slug, Museum.published_at.isnot(None))
        .one_or_none()
    )
    if m is None or qid not in trial_qids(db, m, lang):
        return _not_found()
    obj = db.query(MuseumObject).filter_by(museum_id=m.id, qid=qid).one()
    key = trial_parts(db, obj, lang).get(part)
    if not key:
        return _not_found()
    return RedirectResponse(
        get_object_storage().presigned_url(key, 3600),
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )
