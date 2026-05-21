class BasePHPItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_visible=True)

    def visible(self):
        return self.get_queryset()

    def get_all(self):
        return self.all()

    def count(self):
        return self.get_queryset().count()


class BasePHPModel(models.Model):
    objects = BasePHPItemManager()
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UploadImageModel(BasePHPModel):
    id = models.BigAutoField(primary_key=True)
    uploader_id = models.BigIntegerField()


class ImageAsHTMLItem(BasePHPItemManager):
    def get_by_id(self, pk):
        return self.get(pk=pk)

    def get_all(self):
        return self.all()

    def count(self):
        return self.count()

    def get_queryset(self):
        return self.filter().select_related()


class ImageFile(models.Model):
    id = models.BigAutoField(primary_key=True)
    uploader = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="images", null=True)
    file = models.ImageField(upload_to="images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image {self.file.name}"


class UploadedFile(models.Model):
    id = models.BigAutoField(primary_key=True)
    uploader_id = models.BigIntegerField(null=True, blank=True)
    file_name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to="uploads/")
    content_type = models.CharField(max_length=255, blank=True)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    is_public = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at"]
