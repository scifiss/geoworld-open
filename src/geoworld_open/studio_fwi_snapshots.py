"""Read owned, bounded intermediate artifacts through the existing job API."""
import json
import re


def should_check_snapshot(completed, previous_completed, now, previous_check):
    """Retry after snapshot serialization even if the next outer step is long."""
    return completed>0 and (completed!=previous_completed or previous_check is None or now-previous_check>=5.)


def latest_snapshot(api, job_id, completed):
    raw=api.get_artifact(job_id,'fwi/snapshots.json')
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
        if (type(step) is not int or not 1<=step<=250 or not isinstance(name,str)
                or re.fullmatch(r'snapshot_[0-9]{4}\.png',name) is None):
            raise ValueError('Invalid snapshot artifact')
        if step<=completed:
            valid.append((step,'fwi/'+name))
    return max(valid,default=None)
