"""PUBLIC_SDK_INFRA: field labels and views of server-provided scientific arrays."""
LABELS = {'sand_probability': 'Structure / sand probability', 'porosity': 'Porosity',
    'co2_saturation': 'CO₂ saturation', 'delta_vp': 'P-wave velocity change',
    'delta_far': 'Far-angle PP response change', 'vp': 'P-wave velocity',
    'density': 'Density', 'near': 'Near-angle PP response', 'mid': 'Mid-angle PP response',
    'far': 'Far-angle PP response', 'delta_near': 'Near-angle PP response change',
    'delta_mid': 'Mid-angle PP response change'}
DEFAULT_FIELDS = ('porosity', 'co2_saturation', 'delta_vp', 'delta_far')


def field_label(name):
    return LABELS.get(name, name.replace('_', ' ').capitalize())


def compose_fields(section, fields, *, scale=1., identity=''):
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    ncols = 1 if len(fields)==1 else 2
    rows = (len(fields)+ncols-1)//ncols
    figure = make_subplots(rows=rows, cols=ncols, shared_xaxes=True, shared_yaxes=True,
        subplot_titles=[field_label(name) for name in fields], vertical_spacing=.25,
        horizontal_spacing=.2)
    for index, name in enumerate(fields):
        values = section['fields'][name]
        array = np.asarray(values['values'])
        signed = name.startswith('delta_') or name in {'near','mid','far'}
        bound = max(float(np.abs(array).max()), 1e-12) * scale
        limits = dict(zmin=-bound,zmax=bound) if signed else {}
        row, col = index//ncols+1,index%ncols+1
        figure.add_trace(go.Heatmap(x=np.asarray(section['distance_m'])/1000,
            y=section['time_s'], z=array, colorscale='RdBu' if signed else 'Cividis',
            colorbar=dict(title=dict(text=values['units'],side='bottom'),
                orientation='h', thickness=10, len=.36 if ncols==2 else .75,
                x=.2 if ncols==2 and col==1 else .8 if ncols==2 else .5,
                xanchor='center', yanchor='top', y=.51 if row==1 and rows==2 else -.16,
                tickfont=dict(size=10)),
            **limits),row=row,col=col)
        figure.update_xaxes(title_text='Along-line distance (km)',row=row,col=col)
        figure.update_yaxes(title_text='TWT (s)',autorange='reversed',row=row,col=col)
    figure.update_layout(height=740 if rows==2 else 460,margin=dict(l=60,r=30,t=45,b=110),
        uirevision=identity+'|'.join(fields),font=dict(size=12))
    return figure
