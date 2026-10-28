SELECT p.Name, s.Name FROM dbo.Product p JOIN dbo.ProductSubcategory s ON p.ListPrice > 100;
