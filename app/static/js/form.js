document.addEventListener("DOMContentLoaded", function () {
    var submitBtn = document.getElementById("submit-btn");
    if (!submitBtn) return;

    submitBtn.addEventListener("click", function (e) {
        var rows = document.querySelectorAll("#report-form tbody tr");
        var invalid = false;

        rows.forEach(function (row) {
            var anomalie = row.querySelector(".anomalie-field").value.trim();
            var type = row.querySelector(".type-field").value;
            var cause = row.querySelector(".cause-field").value;
            if (anomalie && (!type || !cause)) {
                invalid = true;
            }
        });

        if (invalid) {
            e.preventDefault();
            alert("Type et Cause sont obligatoires pour chaque anomalie renseignée.");
        }
    });
});
