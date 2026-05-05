document.addEventListener("DOMContentLoaded", function() {
    // Drop-down navigation bar
    let profileDropdownList = document.querySelector(".profile-dropdown-list1");
    let btn1 = document.querySelector(".profile-dropdown-btn1");

    const toggle = () => profileDropdownList.classList.toggle("active");

    btn1.addEventListener("click", toggle);

    window.addEventListener("click", function(e) {
        if (!btn1.contains(e.target) && !profileDropdownList.contains(e.target)) {
            profileDropdownList.classList.remove("active");
        }
    });

    // Select gender 
    function selectGender(image) {
        document.querySelectorAll('.gender-image').forEach(img => {
            img.style.border = 'none';
        });
        image.style.border = '2px solid blue';
        document.getElementById('gender').value = image.dataset.value;
    }
    
    
    // Change profile picture
    const editButton = document.getElementById('edit-profile-photo-btn');
    const fileInput = document.getElementById('new_profile_photo');
    const saveButton = document.getElementById('save-profile-photo-btn');

    editButton.addEventListener('click', () => {
        fileInput.click(); // When click
    });

    fileInput.addEventListener('change', () => {
        saveButton.click(); // Save changes automatically when selecting a file
    });

});
