"""Read owned, bounded intermediate artifacts through the existing job API."""
import json
import re


def snapshot_caption(completed: int, total: int) -> str:
    """Label saved optimizer-update images without mislabelling the final one."""
    if completed < 1 or total < 1 or completed > total:
        raise ValueError("Invalid optimizer-update boundary")
    if completed == total:
        return f"Final FWI result after {completed}/{total} optimizer updates."
    return (
        f"Intermediate FWI result after {completed}/{total} optimizer updates; "
        "not the final result."
    )


def should_check_snapshot(completed, previous_completed, now, previous_check):
    """Retry after snapshot serialization even if the next outer step is long."""
    return completed>0 and (completed!=previous_completed or previous_check is None or now-previous_check>=5.)


def latest_snapshot(api, job_id, completed, *, configurable=False):
    index = 'configurable_fwi_snapshots.json' if configurable else 'fwi/snapshots.json'
    raw=api.get_artifact(job_id,index)
    if len(raw)>32768:
        raise ValueError('Snapshot index exceeds display limit')
    values=json.loads(raw)
    if not isinstance(values,list) or len(values)>10:
        raise ValueError('Invalid snapshot index')
    valid=[]
    for value in values:
        if not isinstance(value,dict):
            raise ValueError('Invalid snapshot entry')
        step=value.get('completed')
        name=value.get('figure_file')
        pattern = r'configurable_fwi_snapshot_[0-9]{4}\.png' if configurable else r'snapshot_[0-9]{4}\.png'
        if (type(step) is not int or not 1<=step<=250 or not isinstance(name,str)
                or re.fullmatch(pattern,name) is None):
            raise ValueError('Invalid snapshot artifact')
        if step<=completed:
            valid.append((step,name if configurable else 'fwi/'+name))
    return max(valid,default=None)
