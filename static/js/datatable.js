$(document).ready(function () {
    $('#trains').DataTable({
        autoWidth: true,
        search: false,
        paging: true,
        ordering: false,
        "language": {
            "lengthMenu": "Zobrazit _MENU_ výsledků na stránku",
            "zeroRecords": "Vlak splňující kritéria nebyl nalezen :(",
            "info": "Stránka _PAGE_ z _PAGES_",
            "infoEmpty": "Nejsou k dispozici žádné záznamy",
            "infoFiltered": "(filtrováno z _MAX_ výsledků)",
            "search": "Hledat: ",
            "paginate": {
                "first": "První",
                "last": "Poslední",
                "next": "Další",
                "previous": "Předchozí"
            }
        }
    });
});