# ZAYVORA MATAB OS — Medical Library Repository Storage

This directory (`./data/medical_books`) is the default location for the 97 classical Tibb compendia, statutory AYUSH formularies, and modern biomedical manuals in production environments.

## Production Server Deployment Instructions:
1. **Directory Location**:
   Upload or copy your PDF and archive files (e.g. *Al-Qanun fi al-Tibb*, *Al-Hawi*, *Robbins*, *NFUM*) into this directory on your live server:
   ```bash
   /path/to/zayvora-matab-os/data/medical_books/
   ```

2. **Custom Disk Path or Mounted Volume**:
   If you store books on a separate block storage volume, SSD, or external drive (e.g., `/var/matab/books`), configure the path in your `.env` file:
   ```bash
   MATAB_BOOKS_DIR=/var/matab/books
   ```

3. **Multi-Environment Auto-Detection**:
   The ZAYVORA MATAB OS backend automatically detects the files using this priority order:
   1. `MATAB_BOOKS_DIR` environment variable from `.env`
   2. Local project directory `./data/medical_books/`
   3. Local project directory `./medical_books/`
   4. Database-registered path (falls back seamlessly during development)

4. **Re-Indexing Catalog**:
   Whenever you add or update books on the server, clinical administrators can re-index the catalog with 1 click from the **📚 Tibb Library** interface via the **"🔄 Refresh Catalog"** button, or via CLI:
   ```bash
   python3 -c "from apps.api.domains.library import MedicalLibraryService; MedicalLibraryService().index_downloaded_books()"
   ```
