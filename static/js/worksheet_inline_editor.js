function getCookie(name) {
    const cookieValue = document.cookie
        .split(";")
        .map((value) => value.trim())
        .find((value) => value.startsWith(`${name}=`));

    if (!cookieValue) {
        return "";
    }

    return decodeURIComponent(cookieValue.split("=").slice(1).join("="));
}

function normalizeInputValue(input) {
    return input.value ?? "";
}

function updateDirtyState(input) {
    const isDirty = normalizeInputValue(input) !== (input.dataset.originalValue ?? "");
    input.classList.toggle("inline-cell-input-dirty", isDirty);
    const cell = input.closest("td");
    if (cell) {
        cell.classList.toggle("inline-cell-dirty", isDirty);
    }
    return isDirty;
}

function collectChanges(root) {
    const changes = [];
    const rows = root.querySelectorAll("tbody tr[data-row-id]");
    rows.forEach((row) => {
        const rowChanges = {};
        row.querySelectorAll("[data-inline-field]").forEach((input) => {
            if (normalizeInputValue(input) !== (input.dataset.originalValue ?? "")) {
                rowChanges[input.dataset.inlineField] = normalizeInputValue(input);
            }
        });
        if (Object.keys(rowChanges).length) {
            changes.push({
                id: row.dataset.rowId,
                changes: rowChanges,
            });
        }
    });
    return changes;
}

function updateToolbar(root) {
    const changes = collectChanges(root);
    const toolbar = root.querySelector("[data-inline-toolbar]");
    const countNode = root.querySelector("[data-change-count]");
    if (!toolbar || !countNode) {
        return;
    }

    countNode.textContent = String(changes.length);
    toolbar.classList.toggle("is-visible", changes.length > 0);
}

async function saveChanges(root) {
    const toolbar = root.querySelector("[data-inline-toolbar]");
    const status = root.querySelector("[data-inline-status]");
    const saveUrl = root.dataset.saveUrl;
    const changes = collectChanges(root);

    if (!saveUrl || !changes.length) {
        return;
    }

    toolbar.classList.add("is-saving");
    if (status) {
        status.textContent = "Saving changes...";
    }

    try {
        const response = await fetch(saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({ rows: changes }),
        });

        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Save failed.");
        }

        root.querySelectorAll("[data-inline-field]").forEach((input) => {
            input.dataset.originalValue = normalizeInputValue(input);
            updateDirtyState(input);
        });
        if (status) {
            status.textContent = `Saved ${payload.updated_count} row${payload.updated_count === 1 ? "" : "s"}.`;
        }
        updateToolbar(root);
    } catch (error) {
        if (status) {
            status.textContent = error.message;
        }
    } finally {
        toolbar.classList.remove("is-saving");
    }
}

function resetChanges(root) {
    root.querySelectorAll("[data-inline-field]").forEach((input) => {
        input.value = input.dataset.originalValue ?? "";
        updateDirtyState(input);
    });
    const status = root.querySelector("[data-inline-status]");
    if (status) {
        status.textContent = "";
    }
    updateToolbar(root);
}

function attachInlineEditor(root) {
    root.querySelectorAll("[data-inline-field]").forEach((input) => {
        input.addEventListener("input", () => {
            updateDirtyState(input);
            updateToolbar(root);
        });
        input.addEventListener("change", () => {
            updateDirtyState(input);
            updateToolbar(root);
        });
    });

    const saveButton = root.querySelector("[data-inline-save]");
    if (saveButton) {
        saveButton.addEventListener("click", () => saveChanges(root));
    }

    const resetButton = root.querySelector("[data-inline-reset]");
    if (resetButton) {
        resetButton.addEventListener("click", () => resetChanges(root));
    }

    window.addEventListener("beforeunload", (event) => {
        if (!collectChanges(root).length) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });
}

document.querySelectorAll("[data-inline-editor-root]").forEach(attachInlineEditor);
