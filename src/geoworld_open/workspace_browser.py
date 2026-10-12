"""PUBLIC_SDK_INFRA: reusable browser assertions for the HTTP-only workspace."""

def settled(page):
    page.wait_for_function("()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning'")
    assert page.get_by_test_id('stException').count() == 0


def select_workspace(page, label):
    page.get_by_role('tab', name=label, exact=True).click()
    settled(page)


def edit_porosity(page, *, row=1, percent=22.):
    """Use the editor's accessible grid keyboard navigation, not session injection."""
    from playwright.sync_api import expect
    grid = page.get_by_test_id('stForm').filter(has=page.get_by_role('button',name='Apply layer edits',exact=True)).get_by_test_id('stDataFrame')
    grid.scroll_into_view_if_needed()
    canvas = grid.locator('canvas').first
    # Glide's scrolling overlay receives pointer events above the canvas.
    grid.locator('.dvn-scroller').click(position={'x':40,'y':52})
    expect(canvas).to_be_focused()
    page.keyboard.press('Control+Home')
    expect(grid.get_by_test_id('glide-cell-0-0')).to_have_attribute('aria-selected','true')
    # Columns: Layer, Lithology, Thickness, Porosity, Vp, Vs, Density.
    for column in range(1,4):
        page.keyboard.press('ArrowRight')
        expect(grid.get_by_test_id(f'glide-cell-{column}-0')).to_have_attribute('aria-selected','true')
    for target_row in range(1,row+1):
        page.keyboard.press('ArrowDown')
        expect(grid.get_by_test_id(f'glide-cell-3-{target_row}')).to_have_attribute('aria-selected','true')
    expect(grid.get_by_test_id(f'glide-cell-3-{row}')).to_have_attribute('aria-readonly','false')
    page.keyboard.press('Enter')
    editor = page.locator('input.gdg-input')
    editor.wait_for()
    editor.fill(str(percent))
    editor.press('Enter')
    page.wait_for_function("args=>Number(document.querySelector(`[data-testid=stForm] [data-testid=glide-cell-3-${args.row}]`)?.textContent)===args.percent",arg={'row':row,'percent':percent})
    page.get_by_role('button',name='Apply layer edits',exact=True).click()
    page.get_by_text('Edited inputs validated for a new experiment. Run simulation when ready; saved results remain unchanged.',exact=True).wait_for()
    settled(page)


def select_fields(page, labels):
    selector = page.get_by_test_id('stMultiSelect').first
    for label in labels:
        selector.locator('input').click()
        page.get_by_role('option',name=label,exact=True).click()
        settled(page)
    page.keyboard.press('Escape')
