"""PUBLIC_SDK_INFRA: reusable browser assertions for the HTTP-only workspace."""

def settled(page):
    # A widget response can arrive just after a previously idle script state.
    page.wait_for_timeout(500)
    page.wait_for_function("()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning'")
    page.wait_for_timeout(300)
    page.wait_for_function("()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning'")
    assert page.get_by_test_id('stException').count() == 0


def select_workspace(page, label):
    page.get_by_role('tab', name=label, exact=True).click()
    settled(page)


def edit_porosity(page, *, row=1, percent=22.):
    """Use the editor's accessible grid keyboard navigation, not session injection."""
    grid = page.get_by_test_id('stDataFrame').first
    grid.scroll_into_view_if_needed()
    canvas = grid.locator('canvas').first
    # Glide's scrolling overlay receives pointer events above the canvas.
    grid.locator('.dvn-scroller').click(position={'x':40,'y':52})
    page.keyboard.press('Control+Home')
    # Columns: Layer, Lithology, Thickness, Porosity, Vp, Vs, Density.
    for _ in range(3): page.keyboard.press('ArrowRight')
    for _ in range(row): page.keyboard.press('ArrowDown')
    page.keyboard.press('Enter')
    editor = page.locator('input.gdg-input')
    editor.wait_for()
    editor.fill(str(percent))
    editor.press('Enter')
    page.wait_for_timeout(700)
    settled(page)
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
