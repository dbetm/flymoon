let allImages = [];
let currentImage = null;

// Load gallery on page load
loadGallery();

function loadGallery() {
    document.getElementById('loadingSpinner').style.display = 'block';
    document.getElementById('galleryGrid').innerHTML = '';
    document.getElementById('emptyState').style.display = 'none';

    fetch('/gallery/list')
        .then(r => r.json())
        .then(images => {
            allImages = images;
            document.getElementById('loadingSpinner').style.display = 'none';
            renderGallery();
        })
        .catch(err => {
            document.getElementById('loadingSpinner').style.display = 'none';
            console.error('Error loading gallery:', err);
        });
}

function renderGallery() {
    const filterTarget = document.getElementById('filterTarget').value;
    const sortOrder = document.getElementById('sortOrder').value;

    let images = allImages.slice();

    if (filterTarget) {
        images = images.filter(img => img.metadata.target === filterTarget);
    }

    images.sort((a, b) => {
        const ta = a.metadata.transit_date || a.metadata.upload_date || '';
        const tb = b.metadata.transit_date || b.metadata.upload_date || '';
        return sortOrder === 'oldest' ? ta.localeCompare(tb) : tb.localeCompare(ta);
    });

    const grid = document.getElementById('galleryGrid');
    const empty = document.getElementById('emptyState');
    const count = document.getElementById('imageCount');

    grid.innerHTML = '';

    count.textContent = `${images.length} image${images.length !== 1 ? 's' : ''}`;

    if (images.length === 0) {
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';

    images.forEach(img => {
        const card = document.createElement('div');
        card.className = 'gallery-card';
        card.onclick = () => openLightbox(img);

        const targetEmoji = img.metadata.target === 'moon' ? '🌙'
                          : img.metadata.target === 'sun'  ? '☀️'
                          : '';

        const flightLabel = img.metadata.flight_id || img.filename;
        const dateLabel = img.metadata.transit_date || '';

        card.innerHTML = `
            <img src="static/${img.path}" alt="${flightLabel}" loading="lazy" />
            <div class="gallery-card-body">
                <div class="gallery-card-title">
                    <span class="gallery-card-target">${targetEmoji}</span>${flightLabel}
                </div>
                <div class="gallery-card-sub">${img.metadata.aircraft_type || ''}${dateLabel ? ' · ' + dateLabel : ''}</div>
                ${img.metadata.caption ? `<div class="gallery-card-sub">${img.metadata.caption}</div>` : ''}
            </div>`;

        grid.appendChild(card);
    });
}

// ── Lightbox ──────────────────────────────────────────────────────────────────

function openLightbox(img) {
    currentImage = img;

    document.getElementById('lightboxImg').src = 'static/' + img.path;
    document.getElementById('lightboxImg').alt = img.metadata.flight_id || img.filename;

    populateMetaTable(img.metadata);

    document.getElementById('lightboxMetaView').style.display = 'block';
    document.getElementById('lightboxMetaEdit').style.display = 'none';

    document.getElementById('lightbox').classList.add('open');
}

function closeLightbox(event) {
    if (event && event.target !== document.getElementById('lightbox')) return;
    document.getElementById('lightbox').classList.remove('open');
    currentImage = null;
}

function populateMetaTable(meta) {
    const rows = [
        ['Flight', meta.flight_id],
        ['Aircraft', meta.aircraft_type],
        ['Target', targetLabel(meta.target)],
        ['Transit date', meta.transit_date || ''],
        ['Uploaded', meta.upload_date ? new Date(meta.upload_date).toLocaleString() : ''],
        ['Caption', meta.caption],
        ['Equipment', meta.equipment],
        ['Transit date', meta.transit_date || ''],
    ];

    const table = document.getElementById('lightboxMetaTable');
    table.innerHTML = rows
        .filter(([, v]) => v)
        .map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`)
        .join('');
}

function targetLabel(target) {
    if (target === 'moon') return '🌙 Moon';
    if (target === 'sun') return '☀️ Sun';
    return target || '';
}

function todayISO() {
    return new Date().toISOString().slice(0, 10);
}

// ── Edit metadata ─────────────────────────────────────────────────────────────

function openEditMode() {
    if (!currentImage) return;
    const meta = currentImage.metadata;
    const form = document.getElementById('editForm');

    form.flight_id.value = meta.flight_id || '';
    form.aircraft_type.value = meta.aircraft_type || '';
    form.target.value = meta.target || '';
    form.caption.value = meta.caption || '';
    form.equipment.value = meta.equipment || '';
    form.transit_date.value = meta.transit_date || todayISO();

    document.getElementById('lightboxMetaView').style.display = 'none';
    document.getElementById('lightboxMetaEdit').style.display = 'block';
}

function closeEditMode() {
    document.getElementById('lightboxMetaView').style.display = 'block';
    document.getElementById('lightboxMetaEdit').style.display = 'none';
}

function submitEdit(event) {
    event.preventDefault();
    if (!currentImage) return;

    const form = document.getElementById('editForm');
    const data = new FormData(form);

    fetch(`/gallery/update/${currentImage.path}`, { method: 'POST', body: data })
        .then(r => r.json())
        .then(result => {
            if (result.success) {
                currentImage.metadata = { ...currentImage.metadata, ...result.metadata };
                // Update in allImages array too
                const idx = allImages.findIndex(i => i.path === currentImage.path);
                if (idx !== -1) allImages[idx].metadata = currentImage.metadata;

                populateMetaTable(currentImage.metadata);
                closeEditMode();
                renderGallery();
            } else {
                alert('Error saving: ' + (result.error || 'Unknown error'));
            }
        })
        .catch(err => {
            console.error('Error updating metadata:', err);
            alert('Error saving metadata.');
        });
}

// ── Delete ────────────────────────────────────────────────────────────────────

function confirmDelete() {
    if (!currentImage) return;
    const label = currentImage.metadata.flight_id || currentImage.filename;
    if (!confirm(`Delete image "${label}"? This cannot be undone.`)) return;

    fetch(`/gallery/delete/${currentImage.path}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(result => {
            if (result.success) {
                allImages = allImages.filter(i => i.path !== currentImage.path);
                document.getElementById('lightbox').classList.remove('open');
                currentImage = null;
                renderGallery();
            } else {
                alert('Error deleting: ' + (result.error || 'Unknown error'));
            }
        })
        .catch(err => {
            console.error('Error deleting image:', err);
            alert('Error deleting image.');
        });
}

// ── Upload modal ──────────────────────────────────────────────────────────────

function openUploadModal() {
    document.getElementById('uploadForm').reset();
    document.getElementById('uploadTransitDate').value = todayISO();
    document.getElementById('uploadPreviewWrap').style.display = 'none';
    document.getElementById('uploadError').style.display = 'none';
    document.getElementById('uploadBtn').disabled = false;
    document.getElementById('uploadBtn').textContent = 'Upload';
    document.getElementById('uploadModal').classList.add('open');
}

function closeUploadModal(event) {
    if (event && event.target !== document.getElementById('uploadModal')) return;
    document.getElementById('uploadModal').classList.remove('open');
}

// Image preview
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('uploadFile').addEventListener('change', function() {
        const file = this.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('uploadPreview').src = e.target.result;
            document.getElementById('uploadPreviewWrap').style.display = 'block';
        };
        reader.readAsDataURL(file);
    });
});

function submitUpload(event) {
    event.preventDefault();

    const form = document.getElementById('uploadForm');
    const errorEl = document.getElementById('uploadError');
    const btn = document.getElementById('uploadBtn');

    errorEl.style.display = 'none';

    const data = new FormData(form);

    btn.disabled = true;
    btn.textContent = 'Uploading…';

    fetch('/gallery/upload', { method: 'POST', body: data })
        .then(r => r.json())
        .then(result => {
            btn.disabled = false;
            btn.textContent = 'Upload';
            if (result.success) {
                document.getElementById('uploadModal').classList.remove('open');
                loadGallery();
            } else {
                errorEl.textContent = result.error || 'Upload failed.';
                errorEl.style.display = 'block';
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.textContent = 'Upload';
            console.error('Upload error:', err);
            errorEl.textContent = 'Network error during upload.';
            errorEl.style.display = 'block';
        });
}
