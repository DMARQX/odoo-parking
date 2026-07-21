// Signature Pad JavaScript for Digital Signatures
// This file handles the signature pad functionality for the digital signature feature

odoo.define('rental_quotation.signature_pad', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var core = require('web.core');

    var _t = core._t;

    // Signature Pad Widget
    var SignaturePad = publicWidget.Widget.extend({
        selector: '.signature-pad-container',
        events: {
            'click #clear_signature': '_onClearSignature',
            'change #agree_terms': '_onTermsChange',
            'click #submit_signature': '_onSubmitSignature',
            'click #reject_signature': '_onRejectSignature',
        },

        init: function () {
            this._super.apply(this, arguments);
            this.signaturePad = null;
            this.canvas = null;
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._initSignaturePad();
                self._bindSignatureEvents();
            });
        },

        _initSignaturePad: function () {
            this.canvas = document.getElementById('signature_pad');
            if (!this.canvas) {
                return;
            }

            // Initialize signature pad
            this.signaturePad = new window.SignaturePad(this.canvas, {
                backgroundColor: 'rgba(255, 255, 255, 0)',
                penColor: 'rgb(0, 0, 0)',
                velocityFilterWeight: 0.7,
                minWidth: 0.5,
                maxWidth: 2.5,
                throttle: 16,
                minPointDistance: 3,
            });

            // Resize canvas
            this._resizeCanvas();
            
            // Handle window resize
            window.addEventListener('resize', this._resizeCanvas.bind(this));
        },

        _resizeCanvas: function () {
            if (!this.canvas || !this.signaturePad) {
                return;
            }

            var ratio = Math.max(window.devicePixelRatio || 1, 1);
            var rect = this.canvas.getBoundingClientRect();
            
            this.canvas.width = rect.width * ratio;
            this.canvas.height = rect.height * ratio;
            this.canvas.getContext('2d').scale(ratio, ratio);
            
            this.signaturePad.clear();
        },

        _bindSignatureEvents: function () {
            var self = this;
            
            if (this.signaturePad) {
                this.signaturePad.addEventListener('beginStroke', function () {
                    self._enableSubmitButton();
                });
                
                this.signaturePad.addEventListener('endStroke', function () {
                    self._updateSignatureData();
                });
            }
        },

        _onClearSignature: function (ev) {
            ev.preventDefault();
            if (this.signaturePad) {
                this.signaturePad.clear();
                this._disableSubmitButton();
                $('#signature_data').val('');
            }
        },

        _onTermsChange: function (ev) {
            this._checkFormValidity();
        },

        _enableSubmitButton: function () {
            this._checkFormValidity();
        },

        _disableSubmitButton: function () {
            $('#submit_signature').prop('disabled', true);
        },

        _checkFormValidity: function () {
            var hasSignature = this.signaturePad && !this.signaturePad.isEmpty();
            var termsAccepted = $('#agree_terms').is(':checked');
            
            $('#submit_signature').prop('disabled', !(hasSignature && termsAccepted));
        },

        _updateSignatureData: function () {
            if (this.signaturePad && !this.signaturePad.isEmpty()) {
                var signatureData = this.signaturePad.toDataURL('image/png');
                $('#signature_data').val(signatureData);
            }
        },

        _onSubmitSignature: function (ev) {
            var self = this;
            ev.preventDefault();
            
            if (!this.signaturePad || this.signaturePad.isEmpty()) {
                this._showError(_t('Please provide your signature before submitting.'));
                return;
            }
            
            if (!$('#agree_terms').is(':checked')) {
                this._showError(_t('Please accept the terms and conditions.'));
                return;
            }

            // Update signature data before submit
            this._updateSignatureData();
            
            // Show loading state
            $('#submit_signature').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Processing...');
            
            // Submit form
            var formData = new FormData($('#signature_form')[0]);
            
            ajax.post('/signature/submit', formData).then(function (result) {
                if (result.success) {
                    window.location.href = result.redirect_url || '/signature/success';
                } else {
                    self._showError(result.error || _t('An error occurred while processing your signature.'));
                    $('#submit_signature').prop('disabled', false).html('<i class="fa fa-check"></i> Sign Document');
                }
            }).catch(function (error) {
                console.error('Signature submission error:', error);
                self._showError(_t('Network error. Please try again.'));
                $('#submit_signature').prop('disabled', false).html('<i class="fa fa-check"></i> Sign Document');
            });
        },

        _onRejectSignature: function (ev) {
            ev.preventDefault();
            var self = this;
            
            // Show confirmation dialog
            if (confirm(_t('Are you sure you want to reject this signature request?'))) {
                var requestId = $('input[name="request_id"]').val();
                
                ajax.post('/signature/reject', {
                    'request_id': requestId,
                    'reason': prompt(_t('Please provide a reason for rejection (optional):')) || ''
                }).then(function (result) {
                    if (result.success) {
                        window.location.href = result.redirect_url || '/';
                    } else {
                        self._showError(result.error || _t('An error occurred while rejecting the signature.'));
                    }
                }).catch(function (error) {
                    console.error('Signature rejection error:', error);
                    self._showError(_t('Network error. Please try again.'));
                });
            }
        },

        _showError: function (message) {
            // Remove existing alerts
            $('.alert-danger').remove();
            
            // Add new alert
            var alertHtml = '<div class="alert alert-danger alert-dismissible fade show" role="alert">' +
                           '<strong>Error:</strong> ' + message +
                           '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                           '<span aria-hidden="true">&times;</span>' +
                           '</button>' +
                           '</div>';
            
            $('.card-body').prepend(alertHtml);
            
            // Auto-hide after 5 seconds
            setTimeout(function () {
                $('.alert-danger').fadeOut();
            }, 5000);
        },

        destroy: function () {
            if (this.signaturePad) {
                this.signaturePad.off();
            }
            window.removeEventListener('resize', this._resizeCanvas.bind(this));
            this._super.apply(this, arguments);
        },
    });

    // Auto-initialize on page load
    publicWidget.registry.SignaturePad = SignaturePad;

    return SignaturePad;
});

// Initialize signature pad when DOM is ready
$(document).ready(function () {
    // Load signature pad library if not already loaded
    if (typeof window.SignaturePad === 'undefined') {
        $.getScript('https://cdn.jsdelivr.net/npm/signature_pad@4.0.0/dist/signature_pad.umd.min.js')
            .done(function () {
                console.log('Signature pad library loaded successfully');
            })
            .fail(function () {
                console.error('Failed to load signature pad library');
                $('.signature-pad-container').html('<div class="alert alert-warning">Signature pad library could not be loaded. Please refresh the page.</div>');
            });
    }
});