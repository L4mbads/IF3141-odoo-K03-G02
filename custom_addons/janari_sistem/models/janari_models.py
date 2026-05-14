import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class Satuan(models.Model):
    _name = 'janari.satuan'
    _description = 'Satuan Bahan Baku'

    name = fields.Char(string='Satuan', required=True)
    category = fields.Selection([
        ('berat', 'Berat'),
        ('volume', 'Volume'),
        ('jumlah', 'Jumlah'),
    ], string='Kategori', required=True, default='jumlah')
    factor = fields.Float(
        string='Faktor ke Satuan Terkecil', default=1.0,
        help='Contoh: Kilogram=1000 (1kg=1000g), Liter=1000 (1L=1000ml), Gram=1'
    )

# D-01 Tabel Bahan Baku
class BahanBaku(models.Model):
    _name = 'janari.bahan.baku'
    _description = 'Tabel Bahan Baku'

    name = fields.Char(string='Nama Bahan', required=True)
    jenis = fields.Char(string='Jenis')
    satuan = fields.Many2one('janari.satuan', string='Satuan')
    harga = fields.Float(string='Harga')
    vendor = fields.Char(string='Vendor')
    stok_saat_ini = fields.Float(string='Stok Saat Ini', default=0)
    reorder_point = fields.Float(string='Reorder Point', default=10)
    is_low_stock = fields.Boolean(string="Status Stok Rendah", compute="_compute_low_stock", store=True)

    def action_new_bahan_baku(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'janari.bahan.baku',
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('stok_saat_ini', 'reorder_point')
    def _compute_low_stock(self):
        for record in self:
            record.is_low_stock = record.stok_saat_ini <= record.reorder_point

# D-04 Tabel Menu
class Menu(models.Model):
    _name = 'janari.menu'
    _description = 'Tabel Menu'

    name = fields.Char(string='Nama Menu', required=True)
    harga_menu = fields.Float(string='Harga Menu', required=True)
    status_menu = fields.Selection([
        ('tersedia', 'Tersedia'),
        ('habis', 'Habis')
    ], string='Status Menu', default='tersedia')
    resep_ids = fields.One2many('janari.resep', 'menu_id', string='Komposisi Resep (BOM)')

# D-03 Tabel Resep (BOM)
class Resep(models.Model):
    _name = 'janari.resep'
    _description = 'Tabel Resep (Bill of Materials)'

    menu_id = fields.Many2one('janari.menu', string='Menu', required=True, ondelete='cascade')
    bahan_baku_id = fields.Many2one('janari.bahan.baku', string='Bahan Baku', required=True)
    jumlah_bahan = fields.Float(string='Jumlah Bahan', required=True)
    satuan = fields.Many2one('janari.satuan', string='Satuan', required=True)

    @api.onchange('bahan_baku_id')
    def _onchange_bahan_baku(self):
        if self.bahan_baku_id and self.bahan_baku_id.satuan:
            self.satuan = self.bahan_baku_id.satuan

# D-05 Tabel Pesanan
class Pesanan(models.Model):
    _name = 'janari.pesanan'
    _description = 'Tabel Pesanan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='ID Pesanan', required=True, copy=False, readonly=True, default=lambda self: 'New')
    tanggal_pesanan = fields.Datetime(string='Tanggal Pesanan', default=fields.Datetime.now)
    nomor_meja = fields.Char(string='Nomor Meja / Antrean')
    sumber_pesanan = fields.Selection([
        ('offline', 'Offline'),
        ('online', 'Online')
    ], string='Sumber Pesanan', default='offline')
    status_pesanan = fields.Selection([
        ('draft', 'Menunggu Pembayaran'),
        ('confirmed', 'Terkonfirmasi'),
        ('done', 'Selesai')
    ], string='Status Keseluruhan', default='draft', tracking=True)
    total_harga = fields.Float(string='Total Harga', compute='_compute_total', store=True)
    detail_pesanan_ids = fields.One2many('janari.detail.pesanan', 'pesanan_id', string='Detail Item')
    transaction_count = fields.Integer(
        string='Jumlah Transaksi',
        compute='_compute_transaction_count',
        store=True
    )

    @api.depends('status_pesanan')
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = 1

    @api.depends('detail_pesanan_ids.subtotal')
    def _compute_total(self):
        for record in self:
            record.total_harga = sum(item.subtotal for item in record.detail_pesanan_ids)

    def _convert_satuan(self, jumlah, dari_satuan, ke_satuan, nama_bahan):
        if not dari_satuan or not ke_satuan or dari_satuan == ke_satuan:
            return jumlah
        if dari_satuan.category != ke_satuan.category:
            raise UserError(
                f"Satuan tidak kompatibel untuk '{nama_bahan}': "
                f"{dari_satuan.name} ({dari_satuan.category}) "
                f"tidak bisa dikonversi ke {ke_satuan.name} ({ke_satuan.category})"
            )
        return jumlah * dari_satuan.factor / ke_satuan.factor

    def action_confirm(self):
        for record in self:
            if record.status_pesanan == 'draft':
                for item in record.detail_pesanan_ids:
                    for resep in item.menu_id.resep_ids:
                        kebutuhan_stok = self._convert_satuan(
                            resep.jumlah_bahan * item.jumlah,
                            resep.satuan,
                            resep.bahan_baku_id.satuan,
                            resep.bahan_baku_id.name,
                        )
                        if resep.bahan_baku_id.stok_saat_ini < kebutuhan_stok:
                            satuan_name = resep.bahan_baku_id.satuan.name or ''
                            raise UserError(
                                f"Stok '{resep.bahan_baku_id.name}' tidak cukup! "
                                f"Dibutuhkan: {kebutuhan_stok} {satuan_name}, "
                                f"Tersedia: {resep.bahan_baku_id.stok_saat_ini}"
                            )
                for item in record.detail_pesanan_ids:
                    for resep in item.menu_id.resep_ids:
                        kebutuhan_stok = self._convert_satuan(
                            resep.jumlah_bahan * item.jumlah,
                            resep.satuan,
                            resep.bahan_baku_id.satuan,
                            resep.bahan_baku_id.name,
                        )
                        resep.bahan_baku_id.stok_saat_ini -= kebutuhan_stok
                record.status_pesanan = 'confirmed'

                low_stock_bahan = record.detail_pesanan_ids.mapped('menu_id.resep_ids.bahan_baku_id').filtered(
                    lambda b: b.stok_saat_ini <= b.reorder_point
                )
                _logger.warning("JANARI DEBUG: low_stock_bahan = %s", low_stock_bahan.mapped('name'))
                if low_stock_bahan:
                    nama_bahan = ', '.join(low_stock_bahan.mapped('name'))
                    channel = self.env['discuss.channel'].sudo().search(
                        [('name', '=', 'general')], limit=1
                    )
                    _logger.warning("JANARI DEBUG: channel = %s", channel)
                    if channel:
                        channel.sudo().message_post(
                            body=f'⚠️ Peringatan Stok Rendah: Stok berikut di bawah reorder point: {nama_bahan}',
                            message_type='comment',
                            subtype_xmlid='mail.mt_comment',
                        )
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Peringatan Stok Rendah',
                            'message': f'Stok berikut di bawah reorder point: {nama_bahan}',
                            'type': 'warning',
                            'sticky': True,
                        }
                    }

# D-06 Tabel Detail Pesanan
class DetailPesanan(models.Model):
    _name = 'janari.detail.pesanan'
    _description = 'Tabel Detail Pesanan'
    _order = 'pesanan_id asc, id asc'

    pesanan_id = fields.Many2one('janari.pesanan', string='Pesanan Reference', required=True, ondelete='cascade')
    menu_id = fields.Many2one('janari.menu', string='Menu', required=True)
    jumlah = fields.Integer(string='Jumlah', default=1, required=True)
    catatan = fields.Char(string='Catatan Khusus')
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal', store=True)
    status_item = fields.Selection([
        ('ordered', 'Ordered'),
        ('processed', 'Processed'),
        ('done', 'Done')
    ], string='Status Dapur (KDS)', default='ordered')
    processed_at = fields.Datetime(string='Waktu Mulai Proses', readonly=True)
    done_at = fields.Datetime(string='Waktu Selesai', readonly=True)
    durasi_tunggu = fields.Integer(
        string='Durasi Tunggu (menit)',
        compute='_compute_durasi',
        store=False,
    )
    update_status_ids = fields.One2many('janari.update.status', 'detail_pesanan_id', string='Riwayat Status')

    # Related fields untuk ditampilkan di KDS kanban card
    nomor_meja = fields.Char(related='pesanan_id.nomor_meja', string='Nomor Meja', store=False, readonly=True)
    tanggal_pesanan = fields.Datetime(related='pesanan_id.tanggal_pesanan', string='Waktu Pesanan', store=False, readonly=True)

    @api.depends('menu_id', 'jumlah')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.menu_id.harga_menu * record.jumlah

    @api.depends('pesanan_id.tanggal_pesanan')
    def _compute_durasi(self):
        now = fields.Datetime.now()
        for record in self:
            if record.pesanan_id and record.pesanan_id.tanggal_pesanan:
                delta = now - record.pesanan_id.tanggal_pesanan
                record.durasi_tunggu = int(delta.total_seconds() / 60)
            else:
                record.durasi_tunggu = 0

    def write(self, vals):
        if 'status_item' in vals:
            logs = []
            for record in self:
                if record.status_item != vals['status_item']:
                    logs.append({
                        'detail_pesanan_id': record.id,
                        'status_before': record.status_item,
                        'status_after': vals['status_item'],
                        'updated_by': self.env.user.sudo().id,
                        'updated_at': fields.Datetime.now(),
                    })
            result = super().write(vals)
            for log_vals in logs:
                self.env['janari.update.status'].create(log_vals)
            return result
        return super().write(vals)

    def action_mulai_proses(self):
        for record in self:
            if record.status_item != 'ordered':
                raise UserError('Hanya item dengan status "Ordered" yang bisa diproses.')
            record.write({
                'status_item': 'processed',
                'processed_at': fields.Datetime.now(),
            })

    def action_selesaikan(self):
        for record in self:
            if record.status_item != 'processed':
                raise UserError('Hanya item dengan status "Processed" yang bisa diselesaikan.')
            record.write({
                'status_item': 'done',
                'done_at': fields.Datetime.now(),
            })
            pesanan = record.pesanan_id
            if all(item.status_item == 'done' for item in pesanan.detail_pesanan_ids):
                pesanan.status_pesanan = 'done'
                pesanan.message_post(
                    body=f'Pesanan <b>{pesanan.name}</b> (Meja {pesanan.nomor_meja or "-"}) sudah selesai dan siap diserahkan ke pelanggan.',
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )

# D-07 Tabel Transaksi
class Transaksi(models.Model):
    _name = 'janari.transaksi'
    _description = 'Tabel Transaksi'

    pesanan_id = fields.Many2one('janari.pesanan', string='Pesanan', required=True)
    metode_pembayaran = fields.Selection([
        ('cash', 'Tunai'),
        ('qris', 'QRIS')
    ], string='Metode Pembayaran', required=True)
    waktu_transaksi = fields.Datetime(string='Waktu Transaksi', default=fields.Datetime.now)
    total_bayar = fields.Float(string='Total Bayar')

# D-08 Tabel Update Status
class UpdateStatus(models.Model):
    _name = 'janari.update.status'
    _description = 'Tabel Riwayat Perubahan Status KDS'
    _order = 'updated_at desc'

    detail_pesanan_id = fields.Many2one('janari.detail.pesanan', string='Item Pesanan', required=True, ondelete='cascade')
    status_before = fields.Char(string='Status Sebelum')
    status_after = fields.Char(string='Status Sesudah')
    updated_by = fields.Many2one('res.users', string='Diubah Oleh', default=lambda self: self.env.user.sudo())
    updated_at = fields.Datetime(string='Waktu Perubahan', default=fields.Datetime.now)
    note = fields.Char(string='Catatan')

class JanariUser(models.Model):
    _inherit = 'res.users'

    janari_role = fields.Selection([
        ('kasir', 'Staf Kasir'),
        ('packer', 'Staf Packer'),
        ('dapur', 'Staf Dapur'),
        ('kepala_staf', 'Kepala Staf'),
        ('pemilik', 'Pemilik')
    ], string='Role Sistem Janari')

    @api.model_create_multi
    def create(self, vals_list):
        users = super(JanariUser, self).create(vals_list)
        for user in users:
            user._update_janari_groups()
        return users

    def write(self, vals):
        res = super(JanariUser, self).write(vals)
        if 'janari_role' in vals:
            self._update_janari_groups()
        return res

    def _update_janari_groups(self):
        for user in self:
            group_map = {
                'kasir': 'janari_sistem.group_janari_kasir',
                'packer': 'janari_sistem.group_janari_packer',
                'dapur': 'janari_sistem.group_janari_dapur',
                'kepala_staf': 'janari_sistem.group_janari_kepala_staf',
                'pemilik': 'janari_sistem.group_janari_pemilik',
            }

            # hapus semua grup Janari agar tidak double role
            all_janari_groups = [self.env.ref(xml_id).id for xml_id in group_map.values() if self.env.ref(xml_id, raise_if_not_found=False)]
            user.write({'groups_id': [(3, gid) for gid in all_janari_groups]})

            if user.janari_role and user.janari_role in group_map:
                group_xml_id = group_map[user.janari_role]
                group = self.env.ref(group_xml_id, raise_if_not_found=False)
                if group:
                    user.write({'groups_id': [(4, group.id)]})