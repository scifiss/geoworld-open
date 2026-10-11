"""PUBLIC_SDK_INFRA: shared navigation and bounded HTTP artifact downloads."""
import json
import io
import hashlib
import zipfile
from pathlib import PurePosixPath
import streamlit as st
from geoworld_open.client import GeoWorldClientError

WORKSPACE_TABS = ('Model & Inputs', 'Scientific Results', 'Evidence & Data', 'Advanced')
PACKAGE_LIMIT_BYTES = 32 * 1024**2


def workspace_tabs(*, completed=False):
    st.markdown('<style>[data-testid="stTabs"] [role="tablist"] {flex-wrap:wrap; height:auto; row-gap:0.2rem;}</style>', unsafe_allow_html=True)
    tabs = st.tabs(WORKSPACE_TABS, default='Scientific Results' if completed else 'Model & Inputs')
    return tabs


def assumption_rows(statements):
    return [{'Assumption': value} for value in dict.fromkeys(statements) if value]


def render_data_downloads(api, job_id, artifacts):
    numerical = [item.name for item in artifacts if PurePosixPath(item.name).suffix in {'.csv', '.npz'}]
    st.markdown('**Numerical data · original stored precision**')
    if numerical:
        selected = st.selectbox('Numerical dataset (CSV / NPZ)', numerical, key='numerical_dataset_'+job_id)
        # The explicit fetch avoids loading every array during every rerender.
        if st.button('Prepare data download', key='prepare_data_'+job_id):
            try:
                st.session_state['workspace_data_download'] = (job_id, selected, api.get_artifact(job_id, selected))
            except GeoWorldClientError as exc:
                st.warning(str(exc))
        saved = st.session_state.get('workspace_data_download')
        if saved and saved[:2] == (job_id, selected):
            st.download_button('Download numerical data', saved[2], file_name=PurePosixPath(selected).name,
                key='download_data_'+job_id, on_click='ignore')
    else:
        st.caption('This saved result has no CSV or NPZ inventory.')
    st.caption('CSV / NPZ contains the saved numerical values; no simulation is run when downloading.')
    candidates = package_inventory(artifacts)
    if candidates:
        if st.button('Prepare numerical data package (ZIP)', key='prepare_package_'+job_id):
            try:
                st.session_state['workspace_data_package'] = (job_id, build_data_package(api, job_id, candidates))
            except (GeoWorldClientError, ValueError) as exc:
                st.warning(str(exc))
        package = st.session_state.get('workspace_data_package')
        if package and package[0] == job_id:
            st.download_button('Download data package (ZIP)',package[1],file_name=f'geoworld-data-{job_id[:8]}.zip',
                mime='application/zip',key='download_package_'+job_id,on_click='ignore')
    elif numerical:
        st.caption('For this inventory, download files individually; combined packages are limited to 32 MiB of recorded source files.')


def package_inventory(artifacts):
    candidates=[item for item in artifacts if PurePosixPath(item.name).suffix in {'.csv','.npz','.json','.yaml'}]
    return candidates if (candidates and all(item.size_bytes is not None and item.size_bytes >= 0 for item in candidates)
        and sum(item.size_bytes for item in candidates) <= PACKAGE_LIMIT_BYTES) else []


def build_data_package(api, job_id, artifacts):
    """Package unchanged HTTP bytes, with a bounded client memory budget."""
    if not package_inventory(artifacts):
        raise ValueError('Package inventory exceeds the bounded download limit or lacks recorded sizes.')
    output=io.BytesIO()
    verification=[]
    total=0
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for item in artifacts:
            path=PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts or '\\' in item.name:
                raise ValueError('Unsafe archive path in artifact inventory.')
            content=api.get_artifact(job_id,item.name)
            total += len(content)
            if len(content)!=item.size_bytes or total>PACKAGE_LIMIT_BYTES:
                raise ValueError('Downloaded artifact size disagrees with recorded inventory.')
            archive.writestr(item.name,content)
            verification.append({'path':item.name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
        archive.writestr('download-manifest.json',json.dumps({'job_id':job_id,'artifacts':verification,
            'scope':'Hashes of downloaded bytes; original scientific provenance remains in saved records.'},indent=2))
    return output.getvalue()


def render_raw_artifacts(api, job_id, result):
    names = [item.name for item in result.artifacts]
    if names:
        selected = st.selectbox('Technical record or artifact', names, key='workspace_raw_'+job_id)
        if st.button('Load technical record', key='workspace_load_raw_'+job_id):
            try:
                st.session_state['workspace_raw_record'] = (job_id, selected, api.get_artifact(job_id, selected))
            except GeoWorldClientError as exc:
                st.warning(str(exc))
        saved = st.session_state.get('workspace_raw_record')
        if saved and saved[:2] == (job_id, selected):
            if selected.endswith('.json'):
                st.json(json.loads(saved[2]), expanded=False)
            st.download_button('Download technical record', saved[2], file_name=PurePosixPath(selected).name,
                key='workspace_raw_download_'+job_id, on_click='ignore')
    with st.expander('Raw specification and result metadata'):
        if result.geospec is not None:
            st.json(result.geospec)
        st.json(result.model_dump(mode='json'), expanded=False)
